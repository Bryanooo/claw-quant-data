#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-claw-quant-data}"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/backups}"
OUTPUT_FILE="${1:-${BACKUP_DIR}/claw-quant-$(date +%Y%m%d-%H%M%S).dump}"
EXCLUDE_TABLE_DATA="${BACKUP_EXCLUDE_TABLE_DATA:-tushare_raw_record}"
BACKUP_COMPRESSION="${BACKUP_COMPRESSION:-zstd:1}"

mkdir -p "$(dirname "${OUTPUT_FILE}")"
TEMP_FILE="${OUTPUT_FILE}.partial"
CHECKSUM_FILE="${OUTPUT_FILE}.sha256"
trap 'rm -f "${TEMP_FILE}" "${CHECKSUM_FILE}.partial"' EXIT

docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
    exec -T postgres sh -c \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl --compress="$2" --exclude-table-data="$1"' \
    _ "${EXCLUDE_TABLE_DATA}" "${BACKUP_COMPRESSION}" \
    > "${TEMP_FILE}"

test -s "${TEMP_FILE}"
docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
    exec -T postgres pg_restore --list < "${TEMP_FILE}" >/dev/null
mv "${TEMP_FILE}" "${OUTPUT_FILE}"
(
    cd "$(dirname "${OUTPUT_FILE}")"
    shasum -a 256 "$(basename "${OUTPUT_FILE}")" \
        > "$(basename "${CHECKSUM_FILE}").partial"
    mv "$(basename "${CHECKSUM_FILE}").partial" \
        "$(basename "${CHECKSUM_FILE}")"
)
trap - EXIT
printf '%s\n' "${OUTPUT_FILE}"
