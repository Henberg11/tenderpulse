"""
Async SQLAlchemy engine + session factory. Import `get_db` as a FastAPI
dependency; import `Base` from here in every model file.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


class Base(DeclarativeBase):
    pass


# Supabase (and most managed Postgres) requires an encrypted connection;
# a plain local/CI Postgres container does not support it and will reject
# a connection that asks for SSL. This MUST stay conditional on a setting --
# an earlier version hardcoded {"ssl": "require"} unconditionally, which
# would have silently broken CI and any local-without-Supabase setup.
_ASYNC_CONNECT_ARGS = {"ssl": "require"} if settings.database_ssl_require else {}

engine = create_async_engine(
    settings.database_url, echo=(settings.environment == "development"), connect_args=_ASYNC_CONNECT_ARGS
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def celery_db_session():
    """Use this instead of AsyncSessionLocal inside Celery tasks.

    FastAPI's `engine` above lives for the whole process and reuses one
    long-running event loop, so connection pooling works fine there. Celery
    tasks are different: each task run wraps its work in `asyncio.run(...)`,
    which creates a brand-new event loop every single call. asyncpg
    connections are tied to the specific event loop they were opened in, so
    reusing the pooled `engine` across separate `asyncio.run()` calls throws
    'cannot perform operation: another operation is in progress' -- the
    connection object survives, but the loop it was born in doesn't.

    This creates a fresh, unpooled engine scoped to just this one task run,
    and disposes it cleanly on the way out. Slightly more overhead per task
    (a few ms to open a connection) in exchange for never hitting this class
    of bug again.
    """
    task_engine = create_async_engine(settings.database_url, poolclass=NullPool, connect_args=_ASYNC_CONNECT_ARGS)
    task_session_factory = async_sessionmaker(task_engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with task_session_factory() as session:
            yield session
    finally:
        await task_engine.dispose()
