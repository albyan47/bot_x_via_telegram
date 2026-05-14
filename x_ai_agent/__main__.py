from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timezone

from .config import settings
from .generator import generate_interactions, generate_posts
from .mobile_export import export_mobile_pack
from .publisher import publish_tweet
from .sources import collect_sources
from .storage import append_jsonl, load_json, read_jsonl, save_json, write_jsonl
from .telegram_sender import (
    get_chat_ids,
    process_manual_references,
    send_approved_drafts_to_telegram,
    send_drafts_to_telegram,
)


def _tweet_id_from_source(source_id: str) -> str | None:
    if source_id.startswith("x:"):
        return source_id.removeprefix("x:")
    return None


def run_once(posts_count: int | None = None, interactions_count: int | None = None) -> int:
    batch_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    state = load_json(settings.state_file, {"used_source_ids": []})
    used = set(state.get("used_source_ids", []))

    sources = [item for item in collect_sources() if item.source_id not in used]
    if not sources:
        raise RuntimeError("Tidak ada sumber baru. Coba tambah sources.yaml atau turunkan MIN_SOURCE_ENGAGEMENT.")

    source_by_id = {source.source_id: source for source in sources}
    posts = generate_posts(sources, settings.posts_per_day if posts_count is None else posts_count)
    interaction_total = settings.interactions_per_day if interactions_count is None else interactions_count
    interactions = generate_interactions(sources, interaction_total) if interaction_total > 0 else []
    now = datetime.now(timezone.utc).isoformat()

    rows = []
    for item in posts + interactions:
        source_id = item.get("source_id", "")
        rows.append(
            {
                "created_at": now,
                "batch_id": batch_id,
                "approved": settings.auto_publish,
                "published": False,
                "published_id": None,
                "kind": item.get("kind", "post"),
                "text": item.get("text", "").strip(),
                "source_id": source_id,
                "source_url": source_by_id[source_id].url if source_id in source_by_id else "",
                "source_title": source_by_id[source_id].title if source_id in source_by_id else "",
                "source_author": source_by_id[source_id].author if source_id in source_by_id else "",
                "reply_to_tweet_id": _tweet_id_from_source(source_id),
                "rationale": item.get("rationale", ""),
            }
        )

    append_jsonl(settings.queue_file, rows)
    state["used_source_ids"] = list((used | {row["source_id"] for row in rows}) - {""})[-500:]
    save_json(settings.state_file, state)

    if settings.auto_publish:
        publish_approved()

    print(f"Created {len(rows)} queue items in {settings.queue_file}")
    return len(rows)


def ensure_today_drafts() -> str:
    today = date.today().isoformat()
    state = load_json(settings.state_file, {"used_source_ids": []})
    daily_batches = state.get("daily_batches", {})
    batch_id = daily_batches.get(today)
    if batch_id:
        return batch_id

    start_index = len(read_jsonl(settings.queue_file))
    run_once()
    rows = read_jsonl(settings.queue_file)
    new_rows = rows[start_index:]
    if not new_rows:
        raise RuntimeError("Tidak ada draft baru yang dibuat.")
    batch_id = new_rows[0].get("batch_id")
    state = load_json(settings.state_file, {"used_source_ids": []})
    daily_batches = state.get("daily_batches", {})
    daily_batches[today] = batch_id
    state["daily_batches"] = daily_batches
    save_json(settings.state_file, state)
    return batch_id


def publish_approved() -> None:
    rows = read_jsonl(settings.queue_file)
    changed = False
    for row in rows:
        if row.get("published") or not row.get("approved"):
            continue
        reply_to = row.get("reply_to_tweet_id") if row.get("kind") == "interaction" else None
        published_id = publish_tweet(row["text"], reply_to_tweet_id=reply_to)
        row["published"] = True
        row["published_id"] = published_id
        row["published_at"] = datetime.now(timezone.utc).isoformat()
        changed = True
        print(f"Published {row['kind']}: {published_id}")

    if changed:
        write_jsonl(settings.queue_file, rows)
    else:
        print("No approved unpublished items found.")


def export_mobile(approved_only: bool = True) -> None:
    count, html_path, txt_path = export_mobile_pack(
        queue_file=settings.queue_file,
        output_html="data/mobile_drafts.html",
        output_txt="data/mobile_drafts.txt",
        approved_only=approved_only,
    )
    print(f"Exported {count} drafts.")
    print(f"HTML: {html_path}")
    print(f"TXT: {txt_path}")


def telegram_chat_ids() -> None:
    chats = get_chat_ids()
    if not chats:
        print("Belum ada chat masuk. Kirim pesan apa saja ke bot Telegram Anda, lalu jalankan lagi.")
        return
    for chat in chats:
        title = chat.get("title") or chat.get("username") or chat.get("first_name") or "-"
        print(f"TELEGRAM_CHAT_ID={chat['id']}  name={title}  type={chat.get('type', '-')}")


def send_telegram(resend: bool = False) -> None:
    count = send_approved_drafts_to_telegram(settings.queue_file, resend=resend)
    print(f"Sent {count} drafts to Telegram.")


def process_telegram_inbox() -> None:
    count = process_manual_references()
    print(f"Processed {count} manual Telegram references.")


def daily_drafts() -> None:
    start_index = len(read_jsonl(settings.queue_file))
    created = run_once()
    sent = send_drafts_to_telegram(
        settings.queue_file,
        approved_only=False,
        start_index=start_index,
    )
    print(f"Daily workflow done. Created {created} drafts, sent {sent} to Telegram.")


def send_today_batch(limit: int) -> None:
    batch_id = ensure_today_drafts()
    sent = send_drafts_to_telegram(
        settings.queue_file,
        approved_only=False,
        limit=limit,
        pending_batch_id=batch_id,
    )
    print(f"Sent {sent} drafts from today's batch {batch_id}.")


def slot_drafts(count: int) -> None:
    start_index = len(read_jsonl(settings.queue_file))
    created = run_once(posts_count=count, interactions_count=0)
    sent = send_drafts_to_telegram(
        settings.queue_file,
        approved_only=False,
        start_index=start_index,
        limit=count,
    )
    print(f"Slot workflow done. Created {created} drafts, sent {sent} to Telegram.")


def run_scheduler() -> None:
    try:
        import schedule
    except ModuleNotFoundError as exc:
        raise RuntimeError("Package schedule belum terpasang. Jalankan: pip install -r requirements.txt") from exc

    schedule.every().day.at("10:00").do(send_today_batch, 2)
    schedule.every().day.at("15:00").do(send_today_batch, 1)
    schedule.every().day.at("19:00").do(send_today_batch, 2)
    print("Scheduler running. Telegram sends: 2 drafts at 10:00, 1 draft at 15:00, 2 drafts at 19:00 WIB/local time.")
    while True:
        schedule.run_pending()
        time.sleep(30)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI X Agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run-once")
    subparsers.add_parser("daily-drafts")
    batch_parser = subparsers.add_parser("send-today-batch")
    batch_parser.add_argument("limit", type=int, help="Jumlah draft dari batch hari ini yang dikirim ke Telegram.")
    slot_parser = subparsers.add_parser("slot-drafts")
    slot_parser.add_argument("count", type=int, help="Jumlah draft baru yang dibuat dan langsung dikirim ke Telegram.")
    subparsers.add_parser("schedule")
    subparsers.add_parser("publish-approved")
    export_parser = subparsers.add_parser("export-mobile")
    export_parser.add_argument("--all", action="store_true", help="Export semua draft, bukan hanya approved yang belum published.")
    subparsers.add_parser("telegram-chat-id")
    subparsers.add_parser("process-telegram-inbox")
    telegram_parser = subparsers.add_parser("send-telegram")
    telegram_parser.add_argument("--resend", action="store_true", help="Kirim ulang draft yang sebelumnya sudah dikirim ke Telegram.")
    args = parser.parse_args()

    if args.command == "run-once":
        run_once()
    elif args.command == "daily-drafts":
        daily_drafts()
    elif args.command == "send-today-batch":
        send_today_batch(args.limit)
    elif args.command == "slot-drafts":
        slot_drafts(args.count)
    elif args.command == "schedule":
        run_scheduler()
    elif args.command == "publish-approved":
        publish_approved()
    elif args.command == "export-mobile":
        export_mobile(approved_only=not args.all)
    elif args.command == "telegram-chat-id":
        telegram_chat_ids()
    elif args.command == "process-telegram-inbox":
        process_telegram_inbox()
    elif args.command == "send-telegram":
        send_telegram(resend=args.resend)


if __name__ == "__main__":
    main()
