#!/bin/sh
# Runs before every container starts (api, worker, beat). Applies any
# pending database migrations automatically -- nobody running this system
# ever needs to type an "alembic" command themselves.
#
# Safe to run in multiple containers starting around the same time: if two
# race on the very first run, one may briefly fail with a "table already
# exists" error -- Docker's restart policy brings it back up seconds later,
# and by then the migration is already applied, so it just proceeds normally.
set -e

echo "[entrypoint] waiting for database..."
ATTEMPT=0
MAX_ATTEMPTS=15

until python -c "
import asyncio
from app.database import engine

async def check():
    async with engine.connect() as conn:
        pass

asyncio.run(check())
"; do
  ATTEMPT=$((ATTEMPT + 1))
  if [ "$ATTEMPT" -ge "$MAX_ATTEMPTS" ]; then
    echo "[entrypoint] giving up after $MAX_ATTEMPTS attempts -- the error above is the real reason. Common cause: DATABASE_URL is wrong, or (if using Supabase) you're using the direct connection string instead of the Connection Pooler string, which most home networks can't reach."
    exit 1
  fi
  echo "[entrypoint] database not ready yet (attempt $ATTEMPT/$MAX_ATTEMPTS), retrying in 3s..."
  sleep 3
done

echo "[entrypoint] applying database migrations..."
alembic upgrade head

echo "[entrypoint] starting: $@"
exec "$@"
