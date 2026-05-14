from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .config import settings


@dataclass(frozen=True)
class SourceItem:
    source_id: str
    source_type: str
    title: str
    text: str
    url: str
    author: str
    published_at: str
    engagement: int


def load_sources() -> dict[str, Any]:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError("Package PyYAML belum terpasang. Jalankan: pip install -r requirements.txt") from exc

    with open(settings.sources_file, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def collect_rss_items(limit_per_feed: int = 5) -> list[SourceItem]:
    try:
        import feedparser
    except ModuleNotFoundError as exc:
        raise RuntimeError("Package feedparser belum terpasang. Jalankan: pip install -r requirements.txt") from exc

    config = load_sources()
    items: list[SourceItem] = []
    for feed in config.get("rss", []):
        parsed = feedparser.parse(feed["url"])
        for entry in parsed.entries[:limit_per_feed]:
            url = entry.get("link", "")
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            published = entry.get("published", "") or datetime.now(timezone.utc).isoformat()
            items.append(
                SourceItem(
                    source_id=_stable_id(feed["name"], url, title),
                    source_type="rss",
                    title=title,
                    text=summary,
                    url=url,
                    author=feed["name"],
                    published_at=published,
                    engagement=0,
                )
            )
    return items


def collect_x_items(max_results_per_account: int = 10) -> list[SourceItem]:
    if not settings.x_bearer_token:
        return []

    try:
        import requests
    except ModuleNotFoundError as exc:
        raise RuntimeError("Package requests belum terpasang. Jalankan: pip install -r requirements.txt") from exc

    config = load_sources()
    handles = config.get("x_accounts", [])
    if not handles:
        return []

    headers = {"Authorization": f"Bearer {settings.x_bearer_token}"}
    usernames = ",".join(handle.lstrip("@") for handle in handles)
    users_resp = requests.get(
        "https://api.twitter.com/2/users/by",
        headers=headers,
        params={"usernames": usernames, "user.fields": "username,name"},
        timeout=20,
    )
    try:
        users_resp.raise_for_status()
    except requests.HTTPError as exc:
        print(f"X source collection skipped: {exc}", file=sys.stderr)
        return []
    users = users_resp.json().get("data", [])

    items: list[SourceItem] = []
    for user in users:
        tweets_resp = requests.get(
            f"https://api.twitter.com/2/users/{user['id']}/tweets",
            headers=headers,
            params={
                "max_results": max_results_per_account,
                "tweet.fields": "created_at,public_metrics",
                "exclude": "retweets,replies",
            },
            timeout=20,
        )
        try:
            tweets_resp.raise_for_status()
        except requests.HTTPError as exc:
            print(f"X tweets skipped for @{user['username']}: {exc}", file=sys.stderr)
            continue
        for tweet in tweets_resp.json().get("data", []):
            metrics = tweet.get("public_metrics", {})
            engagement = (
                metrics.get("like_count", 0)
                + metrics.get("reply_count", 0) * 2
                + metrics.get("retweet_count", 0) * 2
                + metrics.get("quote_count", 0) * 2
            )
            if engagement < settings.min_source_engagement:
                continue
            url = f"https://x.com/{user['username']}/status/{tweet['id']}"
            items.append(
                SourceItem(
                    source_id=f"x:{tweet['id']}",
                    source_type="x",
                    title=f"Post from @{user['username']}",
                    text=tweet.get("text", ""),
                    url=url,
                    author=f"@{user['username']}",
                    published_at=tweet.get("created_at", ""),
                    engagement=engagement,
                )
            )
    return items


def collect_sources() -> list[SourceItem]:
    items = collect_x_items() + collect_rss_items()
    return sorted(items, key=lambda item: item.engagement, reverse=True)
