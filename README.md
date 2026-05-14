# AI X Agent

Agent konten X untuk niche perkembangan AI terbaru dan prediksi arah AI, dengan gaya bahasa Indonesia kasual yang memancing diskusi.

Default agent ini **tidak langsung spam posting/reply**. Ia membuat draft harian dan menyimpannya di `data/queue.jsonl` untuk di-review. Kalau akun X API Anda sudah siap dan Anda memang ingin publish otomatis, aktifkan `AUTO_PUBLISH=true`.

## Fitur

- Minimal 3 draft postingan dan 3 draft interaksi per hari.
- Mengambil inspirasi dari RSS/news resmi dan, bila token tersedia, akun X sumber yang Anda tentukan.
- Menilai kandidat sumber dari engagement publik: like, reply, repost, quote.
- Membuat postingan bahasa Indonesia kasual, diskusi-oriented, dan tidak clickbait murahan.
- Menyimpan log agar tidak mengulang sumber yang sama.
- Bisa publish via X API v2 jika kredensial OAuth 1.0a lengkap.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Jika Windows Anda tidak mengenali `python`, pakai `py`:

```powershell
py -m venv .venv
py -m x_ai_agent --help
```

Isi `.env`:

- `OPENAI_API_KEY`
- `X_BEARER_TOKEN` untuk membaca sumber dari X API
- `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET` untuk publish

## Menjalankan

Buat draft sekali jalan:

```powershell
python -m x_ai_agent run-once
```

Buat draft harian dan langsung kirim ke Telegram:

```powershell
python -m x_ai_agent daily-drafts
```

Jalankan scheduler lokal:

```powershell
python -m x_ai_agent schedule
```

Scheduler akan mengirim draft ke Telegram bertahap:

- 2 draft jam 10:00
- 1 draft jam 15:00
- 2 draft jam 19:00

Jika draft hari itu belum ada, scheduler akan membuat 5 draft dulu lalu mengirim sesuai slot.

## GitHub Actions

Kalau laptop tidak ingin menyala terus, gunakan workflow:

```text
.github/workflows/telegram-drafts.yml
```

Jadwal cloud:

- 10:00 WIB kirim 2 draft
- 15:00 WIB kirim 1 draft
- 19:00 WIB kirim 2 draft

Tambahkan repository secrets berikut di GitHub:

```text
GEMINI_API_KEY
GEMINI_MODEL
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Opsional:

```text
OPENAI_API_KEY
OPENAI_MODEL
X_BEARER_TOKEN
MODEL
```

Catatan: GitHub Actions berjalan di mesin baru setiap jadwal, jadi workflow ini membuat draft baru sesuai slot lalu langsung mengirimnya ke Telegram.

Publish item yang sudah di-approve:

```powershell
python -m x_ai_agent publish-approved
```

Export draft approved ke halaman ramah smartphone:

```powershell
python -m x_ai_agent export-mobile
```

Hasilnya:

```text
data/mobile_drafts.html
data/mobile_drafts.txt
```

Buka HTML di HP untuk copy caption dan cek link sumber referensi sebelum posting manual ke Instagram/X.

Kirim draft approved ke Telegram:

```powershell
python -m x_ai_agent send-telegram
```

Setup Telegram:

1. Buat bot lewat BotFather dan isi `TELEGRAM_BOT_TOKEN` di `.env`.
2. Kirim pesan apa saja ke bot Anda dari Telegram.
3. Jalankan:

```powershell
python -m x_ai_agent telegram-chat-id
```

4. Salin nilai `TELEGRAM_CHAT_ID` ke `.env`.

## Approval Queue

Draft disimpan sebagai JSON Lines di:

```text
data/queue.jsonl
```

Ubah field `"approved": false` menjadi `"approved": true` untuk item yang boleh dipublish.

## Sumber

Edit `sources.yaml`.

- `rss`: sumber berita/blog AI yang stabil.
- `x_accounts`: akun X yang ingin dipantau via X API.

Gunakan akun yang memang relevan dan punya engagement tinggi di niche AI. Hindari menyalin mentah; agent ini membuat angle sendiri, prediksi, dan pertanyaan diskusi.

## Catatan Penting

Otomatisasi X harus hati-hati. Posting berulang, reply generik, dan engagement farming bisa merusak reputasi akun atau melanggar aturan platform. Mode terbaik untuk monetisasi jangka panjang: agent membuat draft cepat, manusia memilih mana yang benar-benar layak.
