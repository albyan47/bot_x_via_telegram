from __future__ import annotations

import json
import re
import time
from typing import Iterable

import requests

from .config import settings
from .sources import SourceItem


SYSTEM_PROMPT = """Anda adalah kreator konten X untuk niche perkembangan AI terbaru.
Tulis dalam bahasa Indonesia kasual, hangat, edukatif, dan memancing diskusi.
Target akun: tumbuh sehat sampai layak monetisasi, bukan engagement farming murahan.

Gaya utama:
- Gunakan gaya ngobrol seperti kreator edukasi Indonesia.
- Boleh pakai pola: "Ada fitur baru...", "Apa itu ...?", "Yuk kita kenalan...", "Kamu punya laptop dan internet...", "Bingung mulai dari mana?"
- Buat pembaca merasa diajak ngobrol, bukan sedang membaca berita kaku.
- Jelaskan konsep dengan sederhana, seperti ngomong ke teman yang penasaran AI.
- Cocok untuk pemula, freelancer, creator, mahasiswa, dan orang yang ingin bangun bisnis digital dengan AI.
- Pakai transisi ringan seperti "nah", "jadi", "singkatnya", "menariknya", "pertanyaannya".
- Akhiri dengan pertanyaan diskusi yang natural kalau ruang karakter cukup.
- Gunakan 1 sampai 2 kalimat saja.
- Tulis seperti manusia yang memang suka bahas AI, bukan seperti output template.
- Jangan menyebut "AI agent", "bot", "otomatis", "draft", atau "sumber mengatakan" di dalam teks posting.
- Hindari struktur yang terlalu rapi atau kaku seperti laporan.

Aturan:
- Jangan menyalin teks sumber.
- Jangan membuat klaim faktual yang tidak ada di sumber.
- Setiap post punya angle edukatif, peluang praktis, prediksi ringan, atau pertanyaan.
- Hindari nada menakut-nakuti seperti "AI akan menggantikan semuanya".
- Jangan pakai hashtag lebih dari 1, dan boleh tanpa hashtag.
- Jangan minta like/retweet/follow.
- Panjang maksimal 240 karakter agar aman untuk X.
- Hindari kata "gila" kecuali benar-benar cocok.
"""


def _openai_client():
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY belum diisi.")
    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:
        raise RuntimeError("Package openai belum terpasang. Jalankan: pip install -r requirements.txt") from exc
    return OpenAI(api_key=settings.openai_api_key)


def _extract_json_array(content: str) -> list[dict]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

    parsed = json.loads(content)
    if isinstance(parsed, list):
        return parsed
    for value in parsed.values():
        if isinstance(value, list):
            return value
    raise ValueError(f"Model tidak mengembalikan JSON array: {content}")


def _gemini_request(prompt: str, model: str) -> requests.Response:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    return requests.post(
        url,
        headers={"x-goog-api-key": settings.gemini_api_key},
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{prompt}\n\nBalas hanya JSON valid."}],
                }
            ],
            "generationConfig": {
                "temperature": 0.8,
                "responseMimeType": "application/json",
            },
        },
        timeout=60,
    )


def _generate_with_gemini(prompt: str) -> list[dict]:
    if not settings.gemini_api_key:
        raise RuntimeError("Isi OPENAI_API_KEY atau GEMINI_API_KEY di .env.")

    models = [settings.gemini_model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    seen: set[str] = set()
    last_error = ""
    for model in models:
        if model in seen:
            continue
        seen.add(model)
        for attempt in range(3):
            response = _gemini_request(prompt, model)
            if response.ok:
                data = response.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                return _extract_json_array(content)
            last_error = f"{response.status_code} {response.reason} saat memakai model {model}"
            if response.status_code not in {429, 500, 502, 503, 504}:
                break
            time.sleep(2 + attempt * 2)
        if response.status_code not in {400, 404, 429, 500, 502, 503, 504}:
            break

    raise RuntimeError(f"Gemini API gagal: {last_error}. Cek GEMINI_MODEL atau API key.")


def _source_block(sources: Iterable[SourceItem]) -> str:
    return "\n\n".join(
        json.dumps(
            {
                "id": item.source_id,
                "type": item.source_type,
                "author": item.author,
                "title": item.title,
                "text": item.text[:700],
                "url": item.url,
                "engagement": item.engagement,
            },
            ensure_ascii=False,
        )
        for item in sources
    )


def generate_posts(sources: list[SourceItem], count: int) -> list[dict]:
    prompt = f"""Buat {count} draft post X dari sumber berikut.

Output JSON array. Setiap item wajib punya:
- kind: "post"
- text
- source_id
- rationale

Variasikan format:
- Edukasi fitur/konsep: "Ada fitur baru di ..., namanya .... Apa itu? Yuk kenalan..."
- Peluang praktis: "Kamu punya laptop, internet, dan pengen mulai bisnis digital? AI bisa bantu dari..."
- Prediksi santai: "Menurutku arah AI berikutnya bukan cuma makin pintar, tapi makin..."
- Tanya diskusi: "Kalau tools seperti ini makin umum, skill apa yang paling penting?"

Sumber:
{_source_block(sources[: max(count * 3, 6)])}
"""
    return _generate_json_array(prompt)


def generate_interactions(sources: list[SourceItem], count: int) -> list[dict]:
    x_sources = [item for item in sources if item.source_type == "x"] or sources
    prompt = f"""Buat {count} draft reply/interaksi X terhadap sumber berikut.

Output JSON array. Setiap item wajib punya:
- kind: "interaction"
- text
- source_id
- interaction_type: "reply"
- rationale

Gaya reply:
- Terdengar seperti manusia yang sedang ngobrol.
- Boleh mulai dengan "Menarik nih", "Nah ini penting", "Aku kepikiran..."
- Tambahkan sudut pandang sederhana, bukan sekadar setuju.
- Ajukan pertanyaan yang enak dijawab oleh akun sumber atau pembaca.
- Jangan terdengar seperti bot.

Sumber:
{_source_block(x_sources[: max(count * 3, 6)])}
"""
    return _generate_json_array(prompt)


def _generate_json_array(prompt: str) -> list[dict]:
    if not settings.openai_api_key:
        return _generate_with_gemini(prompt)

    response = _openai_client().chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    return _extract_json_array(content)
