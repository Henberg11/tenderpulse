# TenderPulse — AI-Powered Tender Intelligence Platform

See `ROADMAP.md` for the phased build plan.
See `docs/AUTONOMY.md` for what's automated vs. what still needs you.

## Setup

1. **Copy the environment file:**
   ```
   copy .env.example .env
   ```
   (Mac/Linux: `cp .env.example .env`)
   The defaults are already correct for running with Docker Compose -- you don't
   need to edit anything to get started. Fill in `OPENAI_API_KEY` later, once you
   reach Phase 2 (document intelligence).

2. **Start everything:**
   ```
   docker compose up --build
   ```
   First run downloads a large base image and can take 15-30 minutes depending on
   your internet speed and disk. On every run after that it's much faster.

3. **You'll know it worked when you see**, from the `api` container:
   ```
   api-1  | [entrypoint] applying database migrations...
   api-1  | INFO:     Application startup complete.
   api-1  | INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

4. **Verify:**
   Open http://localhost:8000/health in a browser -- you should see
   `{"status":"ok","service":"tenderpulse"}`.

   Or from the terminal:
   ```
   docker compose ps
   ```
   All 6 services (postgres, redis, api, worker, beat, backup) should show as
   running, with postgres and api showing "healthy".

## Next concrete step: finish the GeM crawler

This is the single most important next task. Open
`app/crawlers/gem_crawler.py` -- the docstring at the top has a full
step-by-step for filling in the real CSS selectors against the live GeM site.

## API docs

FastAPI auto-generates interactive docs at http://localhost:8000/docs once running.

- `GET /health`
- `GET /tenders` — list, filterable by `status`
- `GET /tenders/{id}` — single tender
- `GET /tenders/{id}/corrigenda` — every detected change to that tender

## If something breaks

The watchdog task will email/Slack you (once configured in `.env`) with a
plain-English explanation and a ready-to-paste technical block. Forward that
message to your AI CTO and it has everything needed to diagnose the issue.
