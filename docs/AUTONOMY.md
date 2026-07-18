# Autonomy & Reliability

What "build it and forget it" actually means here, layer by layer.

## What IS fully autonomous

- **Crawling & ingestion** run on a schedule (Celery beat), no human trigger needed.
- **Corrigendum detection** happens automatically on every crawl.
- **Database setup is automatic.** Every time a container starts, it applies any
  pending migrations itself (`scripts/entrypoint.sh`) -- nobody running this system
  ever needs to type an `alembic` command.
- **Services self-restart** on crash or host reboot (`restart: unless-stopped` on
  every container in `docker-compose.yml`).
- **Failed tasks auto-retry** with exponential backoff.
- **Nightly backups** run automatically and self-prune old ones (`scripts/backup.sh`).
- **The watchdog** (`app/tasks/watchdog_tasks.py`) checks crawler health hourly and
  stays silent unless something's actually wrong. When it does alert, the message is
  written for a non-programmer: a plain-English explanation plus a ready-to-paste
  technical block for a developer (or an AI CTO) to act on.
- **CI blocks broken code** from reaching the always-on server (`.github/workflows/ci.yml`).

## What is NOT and CANNOT be fully autonomous

**Selector drift.** GeM/CPPP will redesign their pages eventually. When that happens,
the crawler will start finding 0 results or erroring, the watchdog will alert once,
and someone needs to inspect the new markup and update the selector in
`gem_crawler.py`. Budget for this as ongoing, occasional maintenance -- a few hours,
a handful of times a year.

**Portal blocking / CAPTCHAs.** Needs a human decision (slow down further? pause and
reassess?), not something to auto-route around.

## The one gap to close yourself: outer-loop monitoring

The watchdog lives *inside* Celery. If Celery itself dies entirely, the watchdog
can't alert you either. Fix: an external monitor outside your infrastructure.

1. Sign up for **UptimeRobot** or **cron-job.org** (free tier is enough).
2. Point it at `GET https://your-domain/health` every 5-15 minutes.
3. Set it to email/SMS you if that endpoint doesn't respond.

## Where to actually deploy this

`docker compose up` on your laptop stops the moment you close the lid. For genuine
unattended operation you need a host that's always on -- a small VPS (DigitalOcean,
Hetzner, AWS Lightsail, ~$5-10/mo) running `docker compose up -d`, with the restart
policies already in place to survive reboots.

## Summary: the actual maintenance burden

With all of the above in place: check email/Slack for the rare watchdog alert, and
expect a few hours a handful of times a year fixing a selector after a portal
redesign. Everything else runs without you.
