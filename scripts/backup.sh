#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-claw-quant-data}"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/backups}"
OUTPUT_FILE="${1:-${BACKUP_DIR}/claw-quant-$(date +%Y%m%d-%H%M%S).dump}"
EXCLUDE_TABLE_DATA="${BACKUP_EXCLUDE_TABLE_DATA:-tushare_raw_record}"
BACKUP_COMPRESSION="${BACKUP_COMPRESSION:-zstd:1}"

mkdir -p "$(dirname "${OUTPUT_FILE}")"
RESERVE_KIB="${BACKUP_FREE_RESERVE_KIB:-5242880}"
case "${RESERVE_KIB}" in ''|*[!0-9]*) printf 'invalid backup reserve\n' >&2; exit 1 ;; esac
latest=$(find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'claw-quant-*.dump' | sort -r | head -1)
expected_kib=0
if [ -n "${latest}" ]; then
    latest_bytes=$(stat -c %s "${latest}" 2>/dev/null || stat -f %z "${latest}")
    expected_kib=$(( (latest_bytes + 1023) / 1024 ))
fi
available_kib() {
    df -Pk "$(dirname "${OUTPUT_FILE}")" | awk 'NR==2 {print $4}'
}
if [ "$(available_kib)" -lt $((expected_kib + RESERVE_KIB)) ]; then
    printf 'insufficient disk space for the next backup and reserve\n' >&2
    exit 1
fi
TEMP_FILE="${OUTPUT_FILE}.partial"
CHECKSUM_FILE="${OUTPUT_FILE}.sha256"
dump_pid=""
cleanup() {
    if [ -n "${dump_pid}" ]; then
        kill "${dump_pid}" 2>/dev/null || true
        wait "${dump_pid}" 2>/dev/null || true
    fi
    rm -f "${TEMP_FILE}" "${CHECKSUM_FILE}.partial"
}
trap cleanup EXIT
trap 'exit 143' TERM INT

docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
    exec -T postgres sh -c \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl --compress="$2" --exclude-table-data="$1"' \
    _ "${EXCLUDE_TABLE_DATA}" "${BACKUP_COMPRESSION}" \
    > "${TEMP_FILE}" &
dump_pid=$!
while kill -0 "${dump_pid}" 2>/dev/null; do
    if [ "$(available_kib)" -le "${RESERVE_KIB}" ]; then
        printf 'backup interrupted: disk space reserve reached\n' >&2
        exit 1
    fi
    sleep 30
done
wait "${dump_pid}"
dump_pid=""

test -s "${TEMP_FILE}"
docker compose -p "${PROJECT_NAME}" -f "${PROJECT_DIR}/docker-compose.yml" \
    exec -T postgres pg_restore --list < "${TEMP_FILE}" >/dev/null
digest=$(shasum -a 256 "${TEMP_FILE}")
printf '%s  %s\n' "${digest%% *}" "$(basename "${OUTPUT_FILE}")" > "${CHECKSUM_FILE}.partial"
mv "${TEMP_FILE}" "${OUTPUT_FILE}"
mv "${CHECKSUM_FILE}.partial" "${CHECKSUM_FILE}"
trap - EXIT
printf '%s\n' "${OUTPUT_FILE}"
