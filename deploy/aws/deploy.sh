#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

if [[ ! -f .env.cloud ]]; then
  echo "Missing .env.cloud. Copy .env.cloud.example and set its values." >&2
  exit 1
fi

if grep -q 'replace-with-output\|ec2-public-ip-or-dns' .env.cloud; then
  echo ".env.cloud still contains placeholder values." >&2
  exit 1
fi

docker compose --env-file .env.cloud \
  -f docker-compose.yml -f docker-compose.cloud.yml \
  config --quiet

docker compose --env-file .env.cloud \
  -f docker-compose.yml -f docker-compose.cloud.yml \
  up -d --build

docker compose --env-file .env.cloud \
  -f docker-compose.yml -f docker-compose.cloud.yml ps

./deploy/aws/smoke-test.sh localhost
