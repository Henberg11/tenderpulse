from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, tenders

app = FastAPI(
    title="TenderPulse",
    description="AI-powered Tender Intelligence Platform",
    version="0.1.0",
)

# CORS_ALLOWED_ORIGINS defaults to "*" for local development. Set it to your
# real dashboard's domain (comma-separated if more than one) in .env before
# this API is ever reachable from the public internet -- "*" means literally
# any website can call it from a user's browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(tenders.router)
