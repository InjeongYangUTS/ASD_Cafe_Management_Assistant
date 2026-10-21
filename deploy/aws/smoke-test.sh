#!/usr/bin/env bash
set -euo pipefail

host="${1:-localhost}"
failed=0

check() {
  local name="$1" url="$2"
  if curl --fail --silent --show-error --max-time 10 "$url" >/dev/null; then
    printf 'PASS  %-24s %s\n' "$name" "$url"
  else
    printf 'FAIL  %-24s %s\n' "$name" "$url"
    failed=1
  fi
}

check "Shared frontend" "http://${host}:5100/"
check "Student 1 frontend" "http://${host}:5110/health"
check "Student 2 frontend" "http://${host}:5200/"
check "Student 3 frontend" "http://${host}:5300/health"
check "Student 4 frontend" "http://${host}:5400/health"
check "Student 5 frontend" "http://${host}:5500/"

exit "$failed"
