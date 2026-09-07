#!/bin/sh

set -eu

backup_dir="${BACKUP_DIR:-/backups}"
interval_seconds="${BACKUP_INTERVAL_SECONDS:-86400}"
retention_days="${BACKUP_RETENTION_DAYS:-14}"
last_success="${backup_dir}/.last-success"

mkdir -p "${backup_dir}"

# Preserve the install/upgrade backup as the first valid daily snapshot rather
# than creating a second large dump immediately when the sidecar is introduced.
if [ ! -s "${last_success}" ] && find "${backup_dir}" -maxdepth 1 \
    -name 'claw-quant-*.dump' -mmin -1440 -print -quit | grep -q .; then
    date +%s > "${last_success}"
fi

while true; do
    now="$(date +%s)"
    previous=0
    if [ -s "${last_success}" ]; then
        previous="$(cat "${last_success}")"
    fi
    if [ $((now - previous)) -ge "${interval_seconds}" ]; then
        stamp="$(date +%Y%m%d-%H%M%S)"
        target="${backup_dir}/claw-quant-${stamp}.dump"
        partial="${target}.partial"
        rm -f "${partial}"
        if pg_dump --format=custom --no-owner --no-acl \
            --file="${partial}" "${PGDATABASE}" && [ -s "${partial}" ]; then
            mv "${partial}" "${target}"
            date +%s > "${last_success}"
            find "${backup_dir}" -maxdepth 1 -type f \
                -name 'claw-quant-*.dump' -mtime "+${retention_days}" -delete
            printf 'backup completed: %s\n' "${target}"
        else
            rm -f "${partial}"
            printf 'backup failed at %s\n' "$(date -Iseconds)" >&2
        fi
    fi
    heartbeat_success=0
    if [ -s "${last_success}" ]; then
        heartbeat_success="$(cat "${last_success}")"
    fi
    backup_instance="$(hostname | tr -cd 'A-Za-z0-9_.-')"
    psql -v ON_ERROR_STOP=1 \
        -c "INSERT INTO sys_service_heartbeat(
                component,instance_id,process_id,last_seen_at,details
            ) VALUES (
                'backup', '${backup_instance}', $$, NOW(),
                jsonb_build_object(
                    'backup_dir','/backups',
                    'last_success_epoch',${heartbeat_success},
                    'interval_seconds',${interval_seconds},
                    'retention_days',${retention_days}
                )
            ) ON CONFLICT(component,instance_id) DO UPDATE SET
                process_id=EXCLUDED.process_id,
                last_seen_at=EXCLUDED.last_seen_at,
                details=EXCLUDED.details" >/dev/null || true
    sleep 60
done
