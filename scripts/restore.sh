#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-claw-quant-data}"
BACKUP_FILE="${1:-}"
shift || true
TARGET_DATABASE=""
CONFIRM=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --database)
            TARGET_DATABASE="${2:-}"
            shift 2
            ;;
        --yes)
            CONFIRM="--yes"
            shift
            ;;
        *)
            printf '未知参数：%s\n' "$1" >&2
            exit 2
            ;;
    esac
done

if [[ -z "${BACKUP_FILE}" || ! -f "${BACKUP_FILE}" ]]; then
    printf '用法：%s /path/to/backup.dump [--database NAME] --yes\n' "$0" >&2
    exit 2
fi
if [[ "${CONFIRM}" != "--yes" ]]; then
    printf '恢复会覆盖当前数据库对象；确认后请追加 --yes。\n' >&2
    exit 2
fi
if [[ -n "${TARGET_DATABASE}" && ! "${TARGET_DATABASE}" =~ ^[A-Za-z][A-Za-z0-9_]{0,62}$ ]]; then
    printf '数据库名只能包含字母、数字、下划线，并且必须以字母开头。\n' >&2
    exit 2
fi

CHECKSUM_FILE="${BACKUP_FILE}.sha256"
if [[ -f "${CHECKSUM_FILE}" ]]; then
    (cd "$(dirname "${BACKUP_FILE}")" && shasum -a 256 -c "$(basename "${CHECKSUM_FILE}")")
fi
docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
    exec -T postgres pg_restore --list < "${BACKUP_FILE}" >/dev/null

PRODUCTION_DATABASE="$(docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
    exec -T postgres sh -c 'printf %s "$POSTGRES_DB"')"
TARGET_DATABASE="${TARGET_DATABASE:-${PRODUCTION_DATABASE}}"
if [[ "${TARGET_DATABASE}" == "${PRODUCTION_DATABASE}" ]]; then
    docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
        stop api worker-v2-routine worker-v2-backfill auditor scheduler
else
    docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
        exec -T postgres sh -c \
        'psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS \"$1\"" -c "CREATE DATABASE \"$1\""' \
        _ "${TARGET_DATABASE}"
fi

docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
    exec -T postgres sh -c \
    'pg_restore -U "$POSTGRES_USER" -d "$1" --clean --if-exists --no-owner --no-acl --exit-on-error' \
    _ "${TARGET_DATABASE}" < "${BACKUP_FILE}"

VALIDATION_SQL="
SELECT
  (SELECT count(*) FROM information_schema.tables
   WHERE table_schema='orchestration_v2'),
  (SELECT count(*) FROM information_schema.tables
   WHERE table_schema='public' AND table_name IN (
     'sys_collection_job', 'sys_collection_job_attempt',
     'sys_collection_fanout_campaign',
     'sys_collection_fanout_campaign_batch',
     'sys_collection_fanout_campaign_entity',
     'sys_collection_initialization',
     'sys_collection_initialization_step',
     'sys_collection_runtime_state',
     'sys_collection_schedule_cursor',
     'sys_collection_delivery_plan', 'sys_collector_run'
   )),
  (SELECT count(*) FROM information_schema.tables
   WHERE table_schema='public' AND table_name IN (
     'stock_basic', 'trade_cal', 'daily'
   )),
  (SELECT count(*) FROM sys_schema_migration
   WHERE version='079_normalize_v2_verified_empty_states'),
  EXISTS (SELECT 1 FROM stock_basic),
  EXISTS (SELECT 1 FROM trade_cal),
  EXISTS (SELECT 1 FROM daily),
  EXISTS (SELECT 1 FROM orchestration_v2.task_definition),
  EXISTS (SELECT 1 FROM orchestration_v2.task_execution_event);
"
docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
    exec -T postgres sh -c \
    'test "$(psql -U "$POSTGRES_USER" -d "$1" -Atc "$2")" = "5|0|3|1|t|t|t|t|t"' \
    _ "${TARGET_DATABASE}" "${VALIDATION_SQL}"

if [[ "${TARGET_DATABASE}" == "${PRODUCTION_DATABASE}" ]]; then
    docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
        up -d api worker-v2-routine worker-v2-backfill auditor scheduler
fi
printf 'restore verified: %s -> %s\n' "${BACKUP_FILE}" "${TARGET_DATABASE}"
