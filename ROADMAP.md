# TenderPulse — Build Roadmap

The vision doc describes the destination. This file describes the order we drive in.
Every phase must be *fully working* before the next one starts.

---

## Compliance note

GeM's `robots.txt` disallows automated access to bid pages, and there's no official
public API for bid listings as of this writing. We're building our own crawler anyway.
Guardrails:

- **Rate limit aggressively.** Space requests out, mimic human browsing pace.
- **Don't spoof identity beyond Playwright's defaults.**
- **Re-check `robots.txt` and GeM's Terms of Use periodically.**
- **Treat this as an operational risk, not just a legal one:** the crawler WILL break
  without warning (layout change, IP block, CAPTCHA). The watchdog task exists for
  exactly this reason.

---

## Phase 0 — Foundation (this scaffold)
- [x] Repo structure, DB models, FastAPI skeleton, Celery/Redis wiring, Docker Compose
- [x] Auto-migration on every container start (no manual `alembic` commands ever needed)
- [x] Watchdog + plain-English diagnostics for non-programmer operators
- [ ] `docker compose up --build` runs clean end to end

**Exit criteria:** `docker compose ps` shows all 6 services running/healthy, and
`http://localhost:8000/health` returns `{"status": "ok"}`.

---

## Phase 1 — Single-Portal Crawler MVP (GeM only)
- [ ] Fill in the real CSS selectors in `app/crawlers/gem_crawler.py` (see the
      step-by-step in that file's docstring)
- [ ] Confirm `python -m app.crawlers.gem_crawler` returns real tender listings
- [ ] Let `crawl_gem` run unattended on the Celery schedule for 7 days with
      < 1% failure rate and zero duplicate tenders

---

## Phase 2 — Document Intelligence
- [ ] PDF/Word text extraction + OCR fallback
- [ ] Structured field extraction via LLM (EMD, dates, eligibility, exemptions)
- [ ] Full-text + embedding search

---

## Phase 3 — Alerts & Dashboard
- [ ] Notification engine wired to real matching tenders (not just watchdog alerts)
- [ ] Minimal React dashboard
- [ ] Manual shortlist/ignore/bidding workflow

---

## Phase 4 — Multi-Portal Expansion
- [ ] Generalize the crawler base class to CPPP, then state portals
- [ ] Per-portal health monitoring

---

## Phase 5 — Knowledge Graph, AI Chat, Competitor Intelligence
Only after Phases 1–4 are stable in production.

---

## Phase 6 — Full Lifecycle OS (long-term north star)
Bid prep, document generation, compliance checking, submission tracking,
post-award execution, invoicing. Treat as a separate product consuming
TenderPulse's data.

---

## Explicit non-goals for v1
- No "winning probability" ML model until there's real historical award data
- No support for portals beyond GeM until Phase 4
- No AI chat assistant until Phase 2's data layer is solid
