#!/bin/sh
# Student 1 (Hangyeol Yi) - Customer Feedback & Reviews
# Database microservice entrypoint.
#
# Seeds the SQLite file on FIRST BOOT ONLY, then serves the /db API.
# Because /app/data is a named Docker volume, a `docker compose down` and
# `up` keeps whatever reviews were written during the demonstration -
# rebuilding the image does not wipe the marker's data.

set -e

DB_FILE="${FEEDBACK_DB_PATH:-/app/data/feedback.db}"
mkdir -p "$(dirname "$DB_FILE")"

if [ ! -f "$DB_FILE" ]; then
    echo "[entrypoint] no database at $DB_FILE - seeding"
    FEEDBACK_DB_PATH="$DB_FILE" python seed.py
else
    echo "[entrypoint] existing database found at $DB_FILE - keeping it"
fi

exec gunicorn --bind "0.0.0.0:${PORT:-7100}" --workers 2 --timeout 60 app:app
