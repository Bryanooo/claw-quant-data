#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-claw-quant-data}"
BACKUP_FILE="${1:-}"
CONFIRM="${2:-}"

if [[ -z "${BACKUP_FILE}" || ! -f "${BACKUP_FILE}" ]]; then
    printf '用法：%s /path/to/backup.dump --yes\n' "$0" >&2
    exit 2
fi
if [[ "${CONFIRM}" != "--yes" ]]; then
    printf '恢复会覆盖当前数据库对象；确认后请追加 --yes。\n' >&2
    exit 2
fi

docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
    stop api worker worker-fanout worker-backfill auditor scheduler
docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
    exec -T postgres sh -c \
    'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-acl' \
    < "${BACKUP_FILE}"
docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
    up -d api worker worker-fanout worker-backfill auditor scheduler
