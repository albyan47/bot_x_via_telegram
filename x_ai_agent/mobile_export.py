from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from .sources import SourceItem, collect_rss_items, collect_x_items
from .storage import ensure_parent, read_jsonl


def _source_index() -> dict[str, SourceItem]:
    items: list[SourceItem] = []
    try:
        items.extend(collect_rss_items(limit_per_feed=30))
    except Exception:
        pass
    try:
        items.extend(collect_x_items(max_results_per_account=20))
    except Exception:
        pass
    return {item.source_id: item for item in items}


def _row_source(row: dict[str, Any], sources: dict[str, SourceItem]) -> dict[str, str]:
    source_id = row.get("source_id", "")
    found = sources.get(source_id)
    return {
        "id": source_id,
        "url": row.get("source_url") or (found.url if found else ""),
        "title": row.get("source_title") or (found.title if found else ""),
        "author": row.get("source_author") or (found.author if found else ""),
    }


def _instagram_caption(text: str) -> str:
    text = text.strip()
    footer = "\n\nSumber referensi ada di catatan/link sumber."
    if len(text) + len(footer) <= 2200:
        return text + footer
    return text


def export_mobile_pack(queue_file: str, output_html: str, output_txt: str, approved_only: bool = True) -> tuple[int, str, str]:
    rows = read_jsonl(queue_file)
    if approved_only:
        rows = [row for row in rows if row.get("approved") and not row.get("published")]

    sources = _source_index()
    cards: list[str] = []
    text_blocks: list[str] = []

    for index, row in enumerate(rows, start=1):
        source = _row_source(row, sources)
        caption = _instagram_caption(row.get("text", ""))
        source_label = source["title"] or source["author"] or source["id"] or "Sumber belum ditemukan"
        source_url = source["url"]

        text_blocks.append(
            "\n".join(
                [
                    f"Draft {index}",
                    f"Tipe: {row.get('kind', '-')}",
                    "",
                    caption,
                    "",
                    f"Sumber: {source_label}",
                    f"Link: {source_url or '-'}",
                    "-" * 48,
                ]
            )
        )

        source_html = (
            f'<a href="{escape(source_url)}" target="_blank" rel="noreferrer">Buka sumber</a>'
            if source_url
            else "<span>Sumber belum ditemukan</span>"
        )
        cards.append(
            f"""
            <article class="card">
              <div class="meta">
                <span>Draft {index}</span>
                <span>{escape(str(row.get("kind", "-")))}</span>
              </div>
              <textarea readonly id="caption-{index}">{escape(caption)}</textarea>
              <div class="actions">
                <button type="button" onclick="copyText('caption-{index}', this)">Copy caption</button>
                {source_html}
              </div>
              <p class="source">{escape(source_label)}</p>
            </article>
            """
        )

    html = f"""<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mobile Drafts</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Arial, sans-serif;
      background: #f6f7f9;
      color: #15171a;
    }}
    body {{
      margin: 0;
      padding: 18px;
    }}
    header {{
      margin: 0 auto 18px;
      max-width: 720px;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 24px;
      letter-spacing: 0;
    }}
    .hint {{
      margin: 0;
      color: #59606a;
      line-height: 1.4;
    }}
    main {{
      display: grid;
      gap: 14px;
      margin: 0 auto;
      max-width: 720px;
    }}
    .card {{
      background: #ffffff;
      border: 1px solid #dfe3e8;
      border-radius: 8px;
      padding: 14px;
    }}
    .meta {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
      color: #59606a;
      font-size: 13px;
      text-transform: uppercase;
    }}
    textarea {{
      box-sizing: border-box;
      width: 100%;
      min-height: 150px;
      border: 1px solid #cbd2da;
      border-radius: 8px;
      padding: 12px;
      resize: vertical;
      font: 16px/1.45 Arial, sans-serif;
      color: #15171a;
      background: #fbfcfd;
    }}
    .actions {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 12px;
      flex-wrap: wrap;
    }}
    button, a {{
      min-height: 42px;
      border-radius: 8px;
      padding: 10px 14px;
      font: 700 15px Arial, sans-serif;
    }}
    button {{
      border: 0;
      background: #1d7f5f;
      color: #ffffff;
    }}
    a {{
      display: inline-flex;
      align-items: center;
      border: 1px solid #cbd2da;
      color: #1d4f91;
      text-decoration: none;
      background: #ffffff;
    }}
    .source {{
      margin: 10px 0 0;
      color: #59606a;
      font-size: 14px;
      line-height: 1.4;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Draft Posting Manual</h1>
    <p class="hint">Buka di HP, copy caption, cek link sumber, lalu posting manual ke Instagram/X.</p>
  </header>
  <main>
    {''.join(cards) if cards else '<p class="hint">Belum ada draft approved yang belum dipublish.</p>'}
  </main>
  <script>
    async function copyText(id, button) {{
      const field = document.getElementById(id);
      await navigator.clipboard.writeText(field.value);
      const original = button.textContent;
      button.textContent = 'Copied';
      setTimeout(() => button.textContent = original, 1200);
    }}
  </script>
</body>
</html>
"""

    ensure_parent(output_html)
    Path(output_html).write_text(html, encoding="utf-8")
    ensure_parent(output_txt)
    Path(output_txt).write_text("\n\n".join(text_blocks), encoding="utf-8")
    return len(rows), output_html, output_txt
