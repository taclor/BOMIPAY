#!/bin/bash
# Restore PostgreSQL database from backup
# Usage: ./scripts/restore.sh backups/bomipay_20240101_120000.sql.gz
# Env vars:
#   DATABASE_URL - PostgreSQL connection URL (required)
set -euo pipefail

BACKUP_FILE=${1:-}

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 backups/bomipay_20240101_120000.sql.gz"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: backup file not found: $BACKUP_FILE"
    exit 1
fi

# Validate required environment variables
if [ -z "${DATABASE_URL:-}" ]; then
    echo "Error: DATABASE_URL environment variable is not set"
    exit 1
fi

echo "[$(date)] Starting restore from $BACKUP_FILE ..."
echo "[$(date)] WARNING: This will overwrite the current database!"
echo "[$(date)] Press Ctrl+C to abort (will timeout in 10 seconds)..."
sleep 10

if gunzip -c "$BACKUP_FILE" | psql "$DATABASE_URL"; then
    echo "[$(date)] Restore complete from $BACKUP_FILE"
    echo "[$(date)] Restore script finished successfully"
else
    echo "[$(date)] Error: Restore failed" >&2
    exit 1
fi
