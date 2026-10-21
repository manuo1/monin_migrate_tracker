#!/usr/bin/env bash
# Backup of the database (pg_dump, custom format) and of the attachments (tar.gz of the media volume).
# Usage: bash scripts/backup.sh [output_dir] [keep_days]
#   output_dir  default: ./backups (git-ignored)
#   keep_days   default: 30 (older backups of this script are deleted; 0 = keep everything)
# Needs the compose stack to be running (docker compose up -d). Run it from anywhere: it moves to the repo root.
set -euo pipefail

# Git Bash on Windows would rewrite /data/media into a Windows path inside docker commands.
export MSYS_NO_PATHCONV=1

cd "$(dirname "$0")/.."

OUT_DIR="${1:-backups}"
KEEP_DAYS="${2:-30}"
STAMP="$(date +%Y%m%d-%H%M%S)"
DB_FILE="$OUT_DIR/mmt-db-$STAMP.dump"
MEDIA_FILE="$OUT_DIR/mmt-media-$STAMP.tar.gz"

mkdir -p "$OUT_DIR"

# Write to a .part file first so a failed run never leaves a truncated file that looks valid.
docker compose exec -T db pg_dump -U mmt -d mmt --format=custom >"$DB_FILE.part"
docker compose exec -T web tar -C /data/media -czf - . >"$MEDIA_FILE.part"

for f in "$DB_FILE" "$MEDIA_FILE"; do
    if [ ! -s "$f.part" ]; then
        echo "ERROR: $f is empty, backup failed." >&2
        rm -f "$DB_FILE.part" "$MEDIA_FILE.part"
        exit 1
    fi
    mv "$f.part" "$f"
done

if [ "$KEEP_DAYS" -gt 0 ]; then
    find "$OUT_DIR" -maxdepth 1 \( -name 'mmt-db-*.dump' -o -name 'mmt-media-*.tar.gz' \) -mtime +"$KEEP_DAYS" -delete
fi

echo "OK: $DB_FILE ($(du -h "$DB_FILE" | cut -f1)), $MEDIA_FILE ($(du -h "$MEDIA_FILE" | cut -f1))"
