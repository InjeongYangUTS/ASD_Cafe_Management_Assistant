#!/bin/sh
# Student 4 - order database microservice entrypoint.
# Seeds the SQLite file on first boot only, then serves the /db API.

set -e

DB_FILE="${ORDER_DB_PATH:-/app/data/orders.db}"
mkdir -p "$(dirname "$DB_FILE")"

if [ ! -f "$DB_FILE" ]; then
    echo "[entrypoint] no database at $DB_FILE - seeding"
    ORDER_DB_PATH="$DB_FILE" python seed.py
else
    echo "[entrypoint] existing database found at $DB_FILE - keeping it"
fi

exec gunicorn --bind "0.0.0.0:${PORT:-7400}" --workers 2 --timeout 60 app:app
