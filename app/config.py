"""
Central configuration. All environment-dependent values live here so nothing
in crawlers/services/routers ever reads os.environ directly.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://tenderpulse:tenderpulse@postgres:5432/tenderpulse"
    database_url_sync: str = "postgresql+psycopg2://tenderpulse:tenderpulse@postgres:5432/tenderpulse"
    # Supabase (and most managed Postgres) requires SSL; a plain local/CI
    # Postgres container does not support it. This MUST be overridable --
    # hardcoding SSL on broke CI and local-without-Supabase setups in an
    # earlier version of this file.
    database_ssl_require: bool = True

    # Redis / Celery
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # AI -- Gemini (free tier: no credit card, generous daily limit, more
    # than enough for a few dozen documents a week). Note: on the free tier
    # Google may use prompt content to improve their models, so this isn't
    # fully private -- acceptable here since tender documents are public
    # government data, not confidential business info.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    openai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"

    # App
    environment: str = "development"
    log_level: str = "INFO"
    storage_dir: str = "./storage/documents"
    # Comma-separated list of allowed origins for the API's CORS policy.
    # "*" (everyone) is fine while this only runs on localhost; tighten this
    # to your real dashboard's domain before this API is ever reachable from
    # the public internet.
    cors_allowed_origins: str = "*"

    # Crawling
    crawl_interval_minutes: int = 45
    gem_base_url: str = "https://bidplus.gem.gov.in"
    cppp_base_url: str = "https://eprocure.gov.in"

    # Notifications
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_email_to: str = ""
    slack_webhook_url: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


settings = Settings()
