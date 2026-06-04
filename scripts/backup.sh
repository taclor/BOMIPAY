#!/bin/bash
# Backup PostgreSQL database and optional files
# Usage: ./scripts/backup.sh
# Env vars:
#   DATABASE_URL - PostgreSQL connection URL (required)
#   BACKUP_DIR   - Directory to store backups (default: ./backups)
#   RETENTION_DAYS - Delete backups older than this (default: 30)
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=${BACKUP_DIR:-./backups}
RETENTION_DAYS=${RETENTION_DAYS:-30}

# Validate required environment variables
if [ -z "${DATABASE_URL:-}" ]; then
    echo "Error: DATABASE_URL environment variable is not set"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

BACKUP_FILE="$BACKUP_DIR/bomipay_$TIMESTAMP.sql.gz"

echo "[$(date)] Starting database backup to $BACKUP_FILE ..."
if pg_dump "$DATABASE_URL" | gzip > "$BACKUP_FILE"; then
    echo "[$(date)] Backup complete: $BACKUP_FILE"
    ls -lh "$BACKUP_FILE"
else
    echo "[$(date)] Error: Backup failed" >&2
    exit 1
fi

# Optional: Backup Redis data if available
REDIS_URL=${REDIS_URL:-}
if [ -n "$REDIS_URL" ]; then
    REDIS_BACKUP="$BACKUP_DIR/redis_$TIMESTAMP.rdb"
    echo "[$(date)] Backing up Redis..."
    redis-cli --raw BGSAVE >/dev/null 2>&1 || echo "Warning: Redis backup skipped"
fi

# Cleanup old backups
echo "[$(date)] Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "bomipay_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete
echo "[$(date)] Backup cleanup complete"

echo "[$(date)] Backup script finished successfully"
