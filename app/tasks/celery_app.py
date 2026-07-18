from celery import Celery

from app.config import settings

celery_app = Celery(
    "tenderpulse",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.crawl_tasks", "app.tasks.watchdog_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
)

# Phase 1: GeM only, every `crawl_interval_minutes`. Add CPPP/state portals
# here in Phase 4 -- each gets its own beat schedule entry, not a code branch.
#
# The watchdog runs on its own independent cadence -- it must NOT be tied to
# the crawl schedule, or a dead Celery beat would silence both the crawler
# AND its own alerting at the same time.
celery_app.conf.beat_schedule = {
    "crawl-gem-every-interval": {
        "task": "app.tasks.crawl_tasks.crawl_gem",
        "schedule": settings.crawl_interval_minutes * 60,
    },
    "watchdog-check-crawler-health": {
        "task": "app.tasks.watchdog_tasks.check_crawler_health",
        "schedule": 60 * 60,
    },
}
