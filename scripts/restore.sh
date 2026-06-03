#!/bin/bash
# Usage: ./scripts/restore.sh backups/bomipay_20240101_120000.sql.gz
# Requires: DATABASE_URL env var pointing to a PostgreSQL database
set -euo pipefail

BACKUP_FILE=${1:-}

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Restoring from $BACKUP_FILE ..."
gunzip -c "$BACKUP_FILE" | psql "$DATABASE_URL"
echo "Restore complete from $BACKUP_FILE"
