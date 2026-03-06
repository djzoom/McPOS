# Kat Records Studio (McPOS Core)

Minimal, production-focused pipeline for generating Kat Records episodes:
playlist → text → cover → mix → render → upload.

## Core Entry Points

- `mcpos_cli.py` (CLI wrapper)
- `mcpos/` (pipeline, assets, adapters)
- `scripts/` (batch + upload helpers)

## Quick Start (CLI)

```bash
# Install dependencies (includes OpenAI client for TEXT_BASE)
python3 -m pip install -r requirements.txt

# Init + run a single episode
python3 mcpos_cli.py init-episode kat kat_20260701
python3 mcpos_cli.py run-episode kat kat_20260701

# Batch produce a month
python3 scripts/batch_produce_month.py kat 2026 7 --skip-completed
```

## Dependencies

- `openai` Python package is required for TEXT_BASE (AI 生成标题/描述/标签).
- Set `OPENAI_API_KEY` or put the key in `config/openai_api_key.txt`.

## Upload (when ready)

```bash
UPLOAD_SCHEDULE_TZ=America/New_York UPLOAD_SCHEDULE_HOUR=9 \
  python3 scripts/upload_when_ready.py --start-date 20260701 --end-date 20260731 --channel kat
```

## Repository Layout (Minimal)

```
mcpos/                 # Pipeline core
scripts/               # Batch + upload helpers
channels/kat/          # Channel data + schedule_master.json
images_pool/           # Image assets
library/               # Audio library
assets/                # Fonts/templates for cover
config/                # Config + OAuth secrets
```

## Notes

- Web UI / T2R stack removed.
- Upload uses `scripts/uploader/upload_to_youtube.py` via McPOS uploader boundary.
