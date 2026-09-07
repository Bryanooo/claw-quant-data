#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-claw-quant-data}"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/backups}"
OUTPUT_FILE="${1:-${BACKUP_DIR}/claw-quant-$(date +%Y%m%d-%H%M%S).dump}"

mkdir -p "$(dirname "${OUTPUT_FILE}")"
TEMP_FILE="${OUTPUT_FILE}.partial"
trap 'rm -f "${TEMP_FILE}"' EXIT

docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
    exec -T postgres sh -c \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' \
    > "${TEMP_FILE}"

test -s "${TEMP_FILE}"
mv "${TEMP_FILE}" "${OUTPUT_FILE}"
trap - EXIT
printf '%s\n' "${OUTPUT_FILE}"
