#!/usr/bin/env bash
# Restore the database and the attachments from a backup made by scripts/backup.sh.
# Usage: bash scripts/restore.sh <db.dump> <media.tar.gz>
# DESTRUCTIVE: replaces the current database content and empties the media volume first.
# Needs the compose stack to exist (docker compose up -d). The web container is stopped during the restore.
set -euo pipefail

# Git Bash on Windows would rewrite /data/media into a Windows path inside docker commands.
export MSYS_NO_PATHCONV=1

if [ "$#" -ne 2 ]; then
    echo "Usage: bash scripts/restore.sh <db.dump> <media.tar.gz>" >&2
    exit 2
fi

DB_FILE="$1"
MEDIA_FILE="$2"
for f in "$DB_FILE" "$MEDIA_FILE"; do
    if [ ! -s "$f" ]; then
        echo "ERROR: $f not found or empty." >&2
        exit 1
    fi
done

# Resolve the paths before moving to the repo root: they were given relative to the caller's directory.
DB_FILE="$(cd "$(dirname "$DB_FILE")" && pwd)/$(basename "$DB_FILE")"
MEDIA_FILE="$(cd "$(dirname "$MEDIA_FILE")" && pwd)/$(basename "$MEDIA_FILE")"

cd "$(dirname "$0")/.."

echo "This REPLACES the current database and attachments with:"
echo "  $DB_FILE"
echo "  $MEDIA_FILE"
read -r -p "Type 'yes' to continue: " answer
if [ "$answer" != "yes" ]; then
    echo "Cancelled."
    exit 1
fi

docker compose up -d db
docker compose stop web

docker compose exec -T db pg_restore -U mmt -d mmt --clean --if-exists --no-owner <"$DB_FILE"

docker compose run --rm --no-deps -T web \
    sh -c 'find /data/media -mindepth 1 -delete && tar -xzf - -C /data/media' <"$MEDIA_FILE"

docker compose up -d web
echo "OK: restore done."
