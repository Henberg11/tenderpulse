"""
Import every model here so Alembic's autogenerate can discover them via
Base.metadata, and so the rest of the app can `from app.models import Tender`.
"""
from app.models.organisation import Organisation
from app.models.tender import Tender, TenderStatus, PortalSource
from app.models.document import TenderDocument
from app.models.corrigendum import Corrigendum
from app.models.crawl_run import CrawlRun, CrawlRunStatus

__all__ = [
    "Organisation",
    "Tender",
    "TenderStatus",
    "PortalSource",
    "TenderDocument",
    "Corrigendum",
    "CrawlRun",
    "CrawlRunStatus",
]
