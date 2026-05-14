from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from .config import settings
from .mobile_export import _instagram_caption, _row_source, _source_index
from .storage import read_jsonl, write_jsonl


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
