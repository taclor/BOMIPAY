#!/bin/bash
# Usage: ./scripts/backup.sh
# Requires: DATABASE_URL env var pointing to a PostgreSQL database
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=${BACKUP_DIR:-./backups}

mkdir -p "$BACKUP_DIR"

BACKUP_FILE="$BACKUP_DIR/bomipay_$TIMESTAMP.sql.gz"

echo "Starting backup to $BACKUP_FILE ..."
pg_dump "$DATABASE_URL" | gzip > "$BACKUP_FILE"
echo "Backup complete: $BACKUP_FILE"
