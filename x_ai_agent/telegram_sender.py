from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import requests

from .config import settings
from .generator import generate_manual_draft
from .mobile_export import _instagram_caption, _row_source, _source_index
from .storage import read_jsonl, write_jsonl


URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)


def _html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _telegram_api(method: str) -> str:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN belum diisi di .env.")
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"


def get_chat_ids() -> list[dict[str, Any]]:
    response = requests.get(_telegram_api("getUpdates"), timeout=20)
    response.raise_for_status()
    chats: dict[int, dict[str, Any]] = {}
    for update in response.json().get("result", []):
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat")
        if chat:
            chats[chat["id"]] = chat
    return list(chats.values())


def _send_message(text: str, source_url: str = "") -> None:
    if not settings.telegram_chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID belum diisi di .env.")

    payload: dict[str, Any] = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if source_url:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "Buka sumber referensi", "url": source_url}]]
        }

    response = requests.post(_telegram_api("sendMessage"), json=payload, timeout=20)
    response.raise_for_status()


def _ack_updates(max_update_id: int) -> None:
    requests.get(
        _telegram_api("getUpdates"),
        params={"offset": max_update_id + 1, "limit": 1},
        timeout=20,
    ).raise_for_status()


def _manual_reference_from_text(text: str) -> tuple[str, str] | None:
    cleaned = text.strip()
    if not cleaned or cleaned.startswith("/"):
        return None

    lowered = cleaned.lower()
    if lowered.startswith("ref:"):
        cleaned = cleaned[4:].strip()
    elif lowered.startswith("referensi:"):
        cleaned = cleaned[10:].strip()
    elif len(cleaned) < 40 and not URL_PATTERN.search(cleaned):
        return None

    urls = URL_PATTERN.findall(cleaned)
    source_url = urls[0].rstrip(").,") if urls else ""
    source_text = URL_PATTERN.sub("", cleaned).strip()
    if not source_text:
        source_text = cleaned
    return source_text, source_url


def process_manual_references() -> int:
    if not settings.telegram_chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID belum diisi di .env.")

    response = requests.get(_telegram_api("getUpdates"), params={"limit": 20}, timeout=20)
    response.raise_for_status()
    updates = response.json().get("result", [])
    processed = 0
    max_update_id = 0

    for update in updates:
        max_update_id = max(max_update_id, update.get("update_id", 0))
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        if str(chat.get("id")) != str(settings.telegram_chat_id):
            continue
        text = message.get("text") or message.get("caption") or ""
        parsed = _manual_reference_from_text(text)
        if not parsed:
            continue

        source_text, source_url = parsed
        draft = generate_manual_draft(source_text=source_text, source_url=source_url)
        caption = _instagram_caption(draft.get("text", "").strip())
        reply = "\n".join(
            [
                "<b>Draft dari referensi manual</b>",
                "",
                "<b>Caption:</b>",
                f"<pre>{_html(caption)}</pre>",
                "",
                "<b>Sumber:</b>",
                _html(source_url or "Teks manual dari Telegram"),
            ]
        )
        _send_message(reply, source_url=source_url)
        processed += 1

    if max_update_id:
        _ack_updates(max_update_id)
    return processed


def send_drafts_to_telegram(
    queue_file: str,
    resend: bool = False,
    approved_only: bool = True,
    start_index: int = 0,
    limit: int | None = None,
    pending_batch_id: str | None = None,
) -> int:
    rows = read_jsonl(queue_file)
    sources = _source_index()
    sent_count = 0

    for index, row in enumerate(rows, start=1):
        if index <= start_index:
            continue
        if approved_only and not row.get("approved"):
            continue
        if row.get("published"):
            continue
        if row.get("sent_to_telegram") and not resend:
            continue
        if pending_batch_id and row.get("batch_id") != pending_batch_id:
            continue

        source = _row_source(row, sources)
        caption = _instagram_caption(row.get("text", ""))
        source_label = source["title"] or source["author"] or source["id"] or "Sumber belum ditemukan"
        source_url = source["url"]

        message = "\n".join(
            [
                f"<b>Draft {index}</b> | {_html(str(row.get('kind', '-')))}",
                "",
                "<b>Caption:</b>",
                f"<pre>{_html(caption)}</pre>",
                "",
                f"<b>Sumber:</b> {_html(source_label)}",
                f"{_html(source_url) if source_url else 'Link sumber belum ditemukan'}",
            ]
        )
        _send_message(message, source_url=source_url)
        row["sent_to_telegram"] = True
        row["sent_to_telegram_at"] = datetime.now(timezone.utc).isoformat()
        sent_count += 1
        if limit is not None and sent_count >= limit:
            break

    if sent_count:
        write_jsonl(queue_file, rows)
    return sent_count


def send_approved_drafts_to_telegram(queue_file: str, resend: bool = False) -> int:
    return send_drafts_to_telegram(queue_file, resend=resend, approved_only=True)
