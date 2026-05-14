from __future__ import annotations

from .config import settings


def can_publish() -> bool:
    return all(
        [
            settings.x_api_key,
            settings.x_api_secret,
            settings.x_access_token,
            settings.x_access_token_secret,
        ]
    )


def publish_tweet(text: str, reply_to_tweet_id: str | None = None) -> str:
    if not can_publish():
        raise RuntimeError("Kredensial X API untuk publish belum lengkap.")

    try:
        import requests
        from requests_oauthlib import OAuth1
    except ModuleNotFoundError as exc:
        raise RuntimeError("Package publish belum lengkap. Jalankan: pip install -r requirements.txt") from exc

    auth = OAuth1(
        settings.x_api_key,
        settings.x_api_secret,
        settings.x_access_token,
        settings.x_access_token_secret,
    )
    payload: dict = {"text": text}
    if reply_to_tweet_id:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to_tweet_id}

    response = requests.post(
        "https://api.twitter.com/2/tweets",
        json=payload,
        auth=auth,
        timeout=20,
    )
    if not response.ok:
        detail = response.text[:500]
        raise RuntimeError(f"X publish failed: {response.status_code} {response.reason}. Detail: {detail}")
    return response.json()["data"]["id"]
