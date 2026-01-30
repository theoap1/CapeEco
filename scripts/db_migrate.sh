#!/usr/bin/env bash
# CapeEco Database Migration Scripts
# Usage:
#   ./scripts/db_migrate.sh export           Export local DB to backup file
#   ./scripts/db_migrate.sh import <file>    Import backup to target DB
#   ./scripts/db_migrate.sh alembic          Run Alembic migrations (upgrade head)
#   ./scripts/db_migrate.sh rollback         Rollback last Alembic migration

set -euo pipefail

# Source defaults (override via env vars)
LOCAL_HOST="${PGHOST:-localhost}"
LOCAL_PORT="${PGPORT:-5432}"
LOCAL_USER="${PGUSER:-capeeco_user}"
LOCAL_DB="${PGDATABASE:-capeeco}"
BACKUP_DIR="./backups"

case "${1:-help}" in
  export)
    mkdir -p "$BACKUP_DIR"
    FILENAME="$BACKUP_DIR/capeeco_$(date +%Y%m%d_%H%M%S).sql.gz"
    echo "Exporting $LOCAL_DB from $LOCAL_HOST:$LOCAL_PORT..."
    pg_dump -h "$LOCAL_HOST" -p "$LOCAL_PORT" -U "$LOCAL_USER" -d "$LOCAL_DB" \
      --no-owner --no-privileges --schema=capeeco --schema=public \
      | gzip > "$FILENAME"
    echo "Exported to $FILENAME ($(du -h "$FILENAME" | cut -f1))"
    ;;

  import)
    FILE="${2:?Usage: db_migrate.sh import <backup.sql.gz>}"
    TARGET_URL="${DATABASE_URL:?Set DATABASE_URL for target database}"
    echo "Importing $FILE to $TARGET_URL..."
    gunzip -c "$FILE" | psql "$TARGET_URL"
    echo "Import complete"
    ;;

  alembic)
    echo "Running Alembic migrations..."
    python3 -m alembic upgrade head
    echo "Migrations applied"
    ;;

  rollback)
    echo "Rolling back last migration..."
    python3 -m alembic downgrade -1
    echo "Rollback complete"
    ;;

  *)
    echo "Usage: $0 {export|import <file>|alembic|rollback}"
    exit 1
    ;;
esac
