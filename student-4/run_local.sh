#!/usr/bin/env bash
# =====================================================================
# Student 4 (Stella Kwon) - Order & Kitchen Management
# Start the three microservices locally, without Docker.
#
#   ./run_local.sh          start everything (seeds the DB on first run)
#   ./run_local.sh --reset  wipe and re-seed the database first
#   ./run_local.sh --stop   stop the services
#   ./run_local.sh --mock   also start the Student 2 / Student 3 test doubles
#
# Screens:  http://localhost:5400/pos  /kitchen  /status
# =====================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$HERE/.local-pids"

DB_PORT=${DB_PORT:-7400}
BACKEND_PORT=${BACKEND_PORT:-8400}
FRONTEND_PORT=${FRONTEND_PORT:-5400}

stop_services() {
    if [ -f "$PIDFILE" ]; then
        while read -r pid; do
            kill "$pid" 2>/dev/null || true
        done < "$PIDFILE"
        rm -f "$PIDFILE"
    fi

    # Fallback: free the ports even if a previous run crashed before writing
    # its pid file. Without this you get "Address already in use" and the old
    # code keeps serving, which is very confusing while developing.
    if command -v lsof > /dev/null 2>&1; then
        for port in "$DB_PORT" "$BACKEND_PORT" "$FRONTEND_PORT" 8200 8300; do
            pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
            if [ -n "$pids" ]; then
                # shellcheck disable=SC2086
                kill $pids 2>/dev/null || true
            fi
        done
    fi

    echo "stopped."
}

case "${1:-}" in
    --stop) stop_services; exit 0 ;;
    --reset) rm -f "$HERE/database/orders.db" ;;
esac

stop_services >/dev/null 2>&1 || true
: > "$PIDFILE"

if [ ! -f "$HERE/database/orders.db" ]; then
    echo "seeding the order database..."
    ORDER_DB_PATH="$HERE/database/orders.db" python3 "$HERE/database/seed.py"
fi

echo "starting student-4-database  on :$DB_PORT"
ORDER_DB_PATH="$HERE/database/orders.db" PORT=$DB_PORT \
    nohup python3 "$HERE/database/app.py" > /tmp/s4-database.log 2>&1 < /dev/null &
echo $! >> "$PIDFILE"
disown
sleep 2

echo "starting student-4-backend   on :$BACKEND_PORT"
( cd "$HERE/backend" && \
  DB_SERVICE_URL="http://localhost:$DB_PORT" \
  MENU_SERVICE_URL="${MENU_SERVICE_URL:-http://localhost:8200}" \
  INVENTORY_SERVICE_URL="${INVENTORY_SERVICE_URL:-http://localhost:8300}" \
  OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}" \
  OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2}" \
  PORT=$BACKEND_PORT nohup python3 app.py > /tmp/s4-backend.log 2>&1 < /dev/null & \
  echo $! >> "$PIDFILE"; disown )
sleep 2

echo "starting student-4-frontend  on :$FRONTEND_PORT"
( cd "$HERE/frontend" && \
  BACKEND_URL="http://localhost:$BACKEND_PORT" \
  SHARED_DIR="$HERE/../shared" \
  PORT=$FRONTEND_PORT nohup python3 app.py > /tmp/s4-frontend.log 2>&1 < /dev/null & \
  echo $! >> "$PIDFILE"; disown )
sleep 3

if [ "${1:-}" = "--mock" ] || [ "${2:-}" = "--mock" ]; then
    echo "starting Student 2 / Student 3 test doubles on :8200 and :8300"
    nohup python3 "$HERE/tests/mock_peers.py" > /tmp/s4-mocks.log 2>&1 < /dev/null &
    echo $! >> "$PIDFILE"
    disown
    sleep 2
fi

echo
echo "POS            http://localhost:$FRONTEND_PORT/pos"
echo "Kitchen        http://localhost:$FRONTEND_PORT/kitchen"
echo "Order status   http://localhost:$FRONTEND_PORT/status"
echo "Backend health http://localhost:$BACKEND_PORT/api/health"
echo
echo "logs: /tmp/s4-*.log     stop: ./run_local.sh --stop"
