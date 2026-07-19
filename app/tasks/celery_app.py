from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "tenderpulse",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.crawl_tasks", "app.tasks.watchdog_tasks", "app.tasks.digest_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
)

# Two fixed times a day (9:00 AM and 4:30 PM, both India time -- timezone
# above is already set to Asia/Kolkata) instead of a fixed interval. Changed
# after a real crawl took 78.9 minutes with everything this session added
# (document downloads for every genuine tender, multi-page pagination, the
# Gujarat consignee-state safety net) -- that no longer comfortably fits in
# a 45-minute interval, and two runs a day gives each one 6-7 hours of room
# with no risk of overlap, rather than needing to keep trimming scope to fit
# a tighter and tighter window.
#
# The watchdog runs on its own independent cadence -- it must NOT be tied to
# the crawl schedule, or a dead Celery beat would silence both the crawler
# AND its own alerting at the same time.
celery_app.conf.beat_schedule = {
    "crawl-gem-morning": {
        "task": "app.tasks.crawl_tasks.crawl_gem",
        "schedule": crontab(hour=9, minute=0),
    },
    "crawl-gem-afternoon": {
        "task": "app.tasks.crawl_tasks.crawl_gem",
        "schedule": crontab(hour=16, minute=30),
    },
    "watchdog-check-crawler-health": {
        "task": "app.tasks.watchdog_tasks.check_crawler_health",
        "schedule": 60 * 60,
    },
}
