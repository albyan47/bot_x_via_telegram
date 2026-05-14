from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


if load_dotenv:
    load_dotenv()


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    return int(raw)


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", os.getenv("MODEL", "gpt-4.1-mini"))
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", os.getenv("MODEL", "gemini-2.5-flash"))
    auto_publish: bool = _bool_env("AUTO_PUBLISH", False)
    x_bearer_token: str = os.getenv("X_BEARER_TOKEN", "")
    x_api_key: str = os.getenv("X_API_KEY", "")
    x_api_secret: str = os.getenv("X_API_SECRET", "")
    x_access_token: str = os.getenv("X_ACCESS_TOKEN", "")
    x_access_token_secret: str = os.getenv("X_ACCESS_TOKEN_SECRET", "")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    queue_file: str = os.getenv("QUEUE_FILE", "data/queue.jsonl")
    state_file: str = os.getenv("STATE_FILE", "data/state.json")
    sources_file: str = os.getenv("SOURCES_FILE", "sources.yaml")
    posts_per_day: int = _int_env("POSTS_PER_DAY", 3)
    interactions_per_day: int = _int_env("INTERACTIONS_PER_DAY", 3)
    min_source_engagement: int = _int_env("MIN_SOURCE_ENGAGEMENT", 50)


settings = Settings()
