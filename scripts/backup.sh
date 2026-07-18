#!/bin/sh
# Nightly Postgres dump. Keeps the last $RETENTION_DAYS dumps and deletes
# older ones so disk doesn't fill up unattended.
set -e

RETENTION_DAYS="${RETENTION_DAYS:-14}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
FILENAME="tenderpulse_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[backup] dumping database to ${BACKUP_DIR}/${FILENAME}"
pg_dump "$DATABASE_URL_SYNC" | gzip > "${BACKUP_DIR}/${FILENAME}"

echo "[backup] pruning dumps older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -name "tenderpulse_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete

echo "[backup] done: $(ls -lh "${BACKUP_DIR}/${FILENAME}" | awk '{print $5}')"

# Optional: uncomment and configure to also push off-box (recommended --
# local-only backups don't survive a dead disk/host).
# aws s3 cp "${BACKUP_DIR}/${FILENAME}" "s3://your-bucket/tenderpulse-backups/"
