#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-claw-quant-data}"
ENV_FILE="${PROJECT_DIR}/.env"
NON_INTERACTIVE=0
SKIP_TOKEN_CHECK=0
ENV_TUSHARE_TOKEN="${TUSHARE_TOKEN:-}"

info() {
    printf '[INFO] %s\n' "$*"
}

success() {
    printf '[ OK ] %s\n' "$*"
}

warn() {
    printf '[WARN] %s\n' "$*" >&2
}

die() {
    printf '[FAIL] %s\n' "$*" >&2
    exit 1
}

on_error() {
    local exit_code=$?
    printf '[FAIL] 安装在第 %s 行中断（退出码 %s）。\n' "${BASH_LINENO[0]}" "${exit_code}" >&2
    printf '       可运行：docker compose -p %s logs --tail=200\n' "${PROJECT_NAME}" >&2
    exit "${exit_code}"
}
trap on_error ERR

usage() {
    cat <<'EOF'
用法：
  ./install.sh [选项]

选项：
  --project-name NAME    Docker Compose 项目名（默认 claw-quant-data）
  --non-interactive     不提示输入 Tushare Token
  --skip-token-check    不调用 Tushare 验证 Token
  -h, --help            显示帮助

也可以通过环境变量传入配置：
  TUSHARE_TOKEN=... ./install.sh
  COMPOSE_PROJECT_NAME=... ./install.sh

脚本不会删除容器数据卷，可以安全地重复运行。
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project-name)
            [[ $# -ge 2 ]] || die "--project-name 缺少参数"
            PROJECT_NAME="$2"
            shift 2
            ;;
        --non-interactive)
            NON_INTERACTIVE=1
            shift
            ;;
        --skip-token-check)
            SKIP_TOKEN_CHECK=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "未知参数：$1（使用 --help 查看帮助）"
            ;;
    esac
done

compose() {
    docker compose -p "${PROJECT_NAME}" "$@"
}

read_env_value() {
    local key="$1"
    [[ -f "${ENV_FILE}" ]] || return 0
    awk -v key="${key}" '
        index($0, key "=") == 1 {
            sub("^[^=]*=", "")
            print
            exit
        }
    ' "${ENV_FILE}"
}

set_env_value() {
    local key="$1"
    local value="$2"
    local temp_file
    temp_file="$(mktemp "${ENV_FILE}.tmp.XXXXXX")"

    awk -v key="${key}" -v value="${value}" '
        BEGIN { found = 0 }
        index($0, key "=") == 1 {
            print key "=" value
            found = 1
            next
        }
        { print }
        END {
            if (!found) {
                print key "=" value
            }
        }
    ' "${ENV_FILE}" > "${temp_file}"

    mv "${temp_file}" "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
}

generate_password() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 24
    else
        LC_ALL=C od -An -N24 -tx1 /dev/urandom | tr -d ' \n'
    fi
}

ensure_env_value() {
    local key="$1"
    local default_value="$2"
    if [[ -z "$(read_env_value "${key}")" ]]; then
        set_env_value "${key}" "${default_value}"
    fi
}

wait_for_postgres() {
    local container_id
    local state
    local attempt

    container_id="$(compose ps -q postgres)"
    [[ -n "${container_id}" ]] || die "没有找到 PostgreSQL 容器"

    for attempt in $(seq 1 60); do
        state="$(docker inspect \
            --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
            "${container_id}")"
        if [[ "${state}" == "healthy" ]]; then
            return 0
        fi
        if [[ "${state}" == "exited" || "${state}" == "dead" ]]; then
            compose logs --tail=200 postgres
            die "PostgreSQL 容器异常退出"
        fi
        sleep 1
    done

    compose logs --tail=200 postgres
    die "等待 PostgreSQL 健康状态超时"
}

wait_for_api() {
    local container_id
    local state
    local attempt

    container_id="$(compose ps -q api)"
    [[ -n "${container_id}" ]] || die "没有找到 API 容器"

    for attempt in $(seq 1 60); do
        state="$(docker inspect \
            --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
            "${container_id}")"
        if [[ "${state}" == "healthy" ]]; then
            return 0
        fi
        if [[ "${state}" == "unhealthy" || "${state}" == "exited" || "${state}" == "dead" ]]; then
            compose logs --tail=200 api
            die "API 容器未能通过健康检查"
        fi
        sleep 1
    done

    compose logs --tail=200 api
    die "等待 API 健康状态超时"
}

wait_for_component() {
    local component="$1"
    local container_id state attempt
    container_id="$(compose ps -q "${component}")"
    [[ -n "${container_id}" ]] || die "没有找到 ${component} 容器"
    for attempt in $(seq 1 60); do
        state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}")"
        [[ "${state}" == "healthy" ]] && return 0
        if [[ "${state}" == "unhealthy" || "${state}" == "exited" || "${state}" == "dead" ]]; then
            compose logs --tail=200 "${component}"
            die "${component} 未能通过进程心跳健康检查"
        fi
        sleep 1
    done
    compose logs --tail=200 "${component}"
    die "等待 ${component} 健康状态超时"
}

verify_token() {
    compose run --rm --no-deps scheduler python - <<'PY'
from service.db import get_pro

frame = get_pro().trade_cal(
    exchange="SSE",
    start_date="20240101",
    end_date="20240103",
)
if frame is None or frame.empty:
    raise SystemExit("Tushare 鉴权成功，但 trade_cal 未返回验证数据")
print(f"Tushare Token 验证成功（trade_cal 返回 {len(frame)} 行）")
PY
}

main() {
    cd "${PROJECT_DIR}"

    command -v docker >/dev/null 2>&1 || die "未安装 Docker，请先安装 Docker Desktop"
    docker compose version >/dev/null 2>&1 || die "当前 Docker 不支持 compose 子命令"
    docker info >/dev/null 2>&1 || die "Docker 服务未运行，请先启动 Docker Desktop"

    success "Docker 与 Docker Compose 可用"

    if [[ ! -f "${ENV_FILE}" ]]; then
        umask 077
        {
            printf 'DB_HOST=127.0.0.1\n'
            printf 'DB_PORT=5432\n'
            printf 'DB_NAME=tushare_db\n'
            printf 'DB_USER=tushare\n'
            printf 'DB_PASSWORD=%s\n' "$(generate_password)"
            printf 'TUSHARE_TOKEN=\n'
            printf 'API_BIND_HOST=127.0.0.1\n'
            printf 'API_PORT=8000\n'
            printf 'API_DB_POOL_MIN=1\n'
            printf 'API_DB_POOL_MAX=10\n'
            printf 'API_DB_CONNECT_RETRIES=12\n'
            printf 'API_DB_CONNECT_RETRY_SECONDS=5\n'
            printf 'JOB_POLL_INTERVAL_SECONDS=2\n'
            printf 'JOB_STALE_AFTER_SECONDS=21600\n'
            printf 'JOB_EXECUTION_TIMEOUT_SECONDS=1800\n'
            printf 'JOB_LEASE_SECONDS=120\n'
            printf 'JOB_RECLAIM_INTERVAL_SECONDS=60\n'
            printf 'ROUTINE_WORKER_RESOURCE_CLASSES=scheduled,generic,reference,market,moneyflow,finance,catalog,default\n'
            printf 'FANOUT_WORKER_RESOURCE_CLASSES=fanout\n'
            printf 'BACKFILL_WORKER_RESOURCE_CLASSES=initialization,backfill\n'
            printf 'COVERAGE_POLL_INTERVAL_SECONDS=5\n'
            printf 'COVERAGE_STALE_AFTER_SECONDS=3600\n'
            printf 'COVERAGE_AUTO_REPAIR_ENABLED=true\n'
            printf 'COVERAGE_AUTO_REPAIR_LIMIT=10\n'
            printf 'SERVICE_HEARTBEAT_MAX_AGE_SECONDS=90\n'
            printf 'NOTIFIER_TYPE=log\n'
            printf 'DINGTALK_USER_ID=\n'
        } > "${ENV_FILE}"
        success "已创建 .env 并生成随机数据库密码"
    else
        chmod 600 "${ENV_FILE}"
        info "检测到现有 .env，将保留已有配置"
    fi

    ensure_env_value "DB_HOST" "127.0.0.1"
    ensure_env_value "DB_PORT" "5432"
    ensure_env_value "DB_NAME" "tushare_db"
    ensure_env_value "DB_USER" "tushare"
    ensure_env_value "DB_PASSWORD" "$(generate_password)"
    ensure_env_value "API_BIND_HOST" "127.0.0.1"
    ensure_env_value "API_PORT" "8000"
    ensure_env_value "API_DB_POOL_MIN" "1"
    ensure_env_value "API_DB_POOL_MAX" "10"
    ensure_env_value "API_DB_CONNECT_RETRIES" "12"
    ensure_env_value "API_DB_CONNECT_RETRY_SECONDS" "5"
    ensure_env_value "JOB_POLL_INTERVAL_SECONDS" "2"
    ensure_env_value "JOB_STALE_AFTER_SECONDS" "21600"
    ensure_env_value "JOB_EXECUTION_TIMEOUT_SECONDS" "1800"
    ensure_env_value "JOB_LEASE_SECONDS" "120"
    ensure_env_value "JOB_RECLAIM_INTERVAL_SECONDS" "60"
    ensure_env_value "ROUTINE_WORKER_RESOURCE_CLASSES" "scheduled,generic,reference,market,moneyflow,finance,catalog,default"
    ensure_env_value "FANOUT_WORKER_RESOURCE_CLASSES" "fanout"
    ensure_env_value "BACKFILL_WORKER_RESOURCE_CLASSES" "initialization,backfill"
    ensure_env_value "COVERAGE_POLL_INTERVAL_SECONDS" "5"
    ensure_env_value "COVERAGE_STALE_AFTER_SECONDS" "3600"
    ensure_env_value "COVERAGE_AUTO_REPAIR_ENABLED" "true"
    ensure_env_value "COVERAGE_AUTO_REPAIR_LIMIT" "10"
    ensure_env_value "SERVICE_HEARTBEAT_MAX_AGE_SECONDS" "90"
    ensure_env_value "NOTIFIER_TYPE" "log"

    if [[ -n "${ENV_TUSHARE_TOKEN}" ]]; then
        set_env_value "TUSHARE_TOKEN" "${ENV_TUSHARE_TOKEN}"
        success "已从环境变量写入 Tushare Token"
    elif [[ -z "$(read_env_value "TUSHARE_TOKEN")" && "${NON_INTERACTIVE}" -eq 0 && -t 0 ]]; then
        token=""
        printf '请输入 Tushare Token（直接回车可暂时跳过）：'
        IFS= read -r -s token
        printf '\n'
        if [[ -n "${token}" ]]; then
            set_env_value "TUSHARE_TOKEN" "${token}"
            success "Tushare Token 已写入 .env"
        fi
    fi

    compose config --quiet
    success "Compose 配置检查通过"

    info "构建应用镜像..."
    compose build api

    info "启动 PostgreSQL..."
    compose up -d postgres
    wait_for_postgres
    success "PostgreSQL 已进入 healthy 状态"

    existing_table_count="$(compose exec -T postgres psql \
        -U "$(read_env_value "DB_USER")" \
        -d "$(read_env_value "DB_NAME")" \
        -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")"
    if [[ "${existing_table_count}" -gt 0 ]]; then
        info "升级前备份现有 PostgreSQL 数据..."
        backup_file="$(COMPOSE_PROJECT_NAME="${PROJECT_NAME}" ./scripts/backup.sh)"
        success "数据库备份完成：${backup_file}"
    fi

    info "执行幂等数据库迁移..."
    compose exec -T postgres sh -lc '
        export PGOPTIONS="--client-min-messages=warning"
        for file in /docker-entrypoint-initdb.d/init_*.sql; do
            psql -v ON_ERROR_STOP=1 \
                -U "$POSTGRES_USER" \
                -d "$POSTGRES_DB" \
                -f "$file" >/dev/null
        done
    '

    compose run --rm --no-deps api python scripts/migrate.py

    table_count="$(compose exec -T postgres psql \
        -U "$(read_env_value "DB_USER")" \
        -d "$(read_env_value "DB_NAME")" \
        -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")"
    [[ "${table_count}" -ge 113 ]] || die "数据库表数量异常：${table_count}"
    success "数据库迁移完成，共 ${table_count} 张表"

    info "启动 REST API、三个隔离采集 Worker、覆盖 Auditor 与调度器..."
    compose up -d api worker worker-fanout worker-backfill auditor scheduler

    info "验证调度器到 PostgreSQL 的连接..."
    compose exec -T scheduler python - <<'PY'
import os

from service.db import query

rows = query("SELECT current_database() AS database_name")
if not rows or rows[0]["database_name"] != os.environ["DB_NAME"]:
    raise SystemExit("应用数据库连接验证失败")
print("应用数据库连接验证成功")
PY
    success "调度器数据库配置可用"

    wait_for_api
    success "REST API 已进入 healthy 状态"
    for component in scheduler worker worker-fanout worker-backfill auditor; do
        wait_for_component "${component}"
    done
    success "Scheduler、三个 Worker 资源池、Auditor 进程心跳正常"

    info "验证 REST API..."
    compose exec -T api python - <<'PY'
import json
import os
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/api/health/ready", timeout=5) as response:
    payload = json.load(response)
if payload.get("status") != "ready":
    raise SystemExit(f"REST API readiness 异常: {payload}")

request = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/datasets",
)
with urllib.request.urlopen(request, timeout=5) as response:
    datasets = json.load(response)
if not datasets:
    raise SystemExit("REST API 没有返回注册数据集")

request = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/collection-tasks",
)
with urllib.request.urlopen(request, timeout=5) as response:
    collection_tasks = json.load(response)
if not collection_tasks:
    raise SystemExit("REST API 没有返回可用采集任务")

request = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/collection-overview",
)
with urllib.request.urlopen(request, timeout=10) as response:
    overview = json.load(response)
if overview.get("summary", {}).get("interfaces", 0) < 200:
    raise SystemExit("采集总览没有返回完整接口目录")

request = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/coverage",
)
with urllib.request.urlopen(request, timeout=10) as response:
    coverage = json.load(response)
if coverage.get("summary", {}).get("datasets", 0) < 10:
    raise SystemExit("数据覆盖总览没有返回覆盖规则")

request = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/initialization",
)
with urllib.request.urlopen(request, timeout=5) as response:
    initialization = json.load(response)
if initialization.get("runtime", {}).get("mode") not in {
    "awaiting_initialization", "initializing", "daily"
}:
    raise SystemExit("初始化运行模式异常")

with urllib.request.urlopen("http://127.0.0.1:8000/dashboard", timeout=5) as response:
    dashboard = response.read()
if "采集控制台".encode("utf-8") not in dashboard:
    raise SystemExit("采集 Dashboard 页面异常")
print("REST API 验证成功")
PY

    token_value="$(read_env_value "TUSHARE_TOKEN")"
    if [[ -n "${token_value}" && "${SKIP_TOKEN_CHECK}" -eq 0 ]]; then
        info "验证 Tushare Token..."
        verify_token
        success "Tushare API 可用"
    elif [[ -z "${token_value}" ]]; then
        warn "尚未配置 TUSHARE_TOKEN；服务可启动，但采集任务会失败"
    else
        warn "已按参数跳过 Tushare Token 验证"
    fi

    scheduler_id="$(compose ps -q scheduler)"
    [[ -n "${scheduler_id}" ]] || die "没有找到调度器容器"
    scheduler_state="$(docker inspect --format '{{.State.Status}}' "${scheduler_id}")"
    [[ "${scheduler_state}" == "running" ]] || {
        compose logs --tail=200 scheduler
        die "调度器未正常运行"
    }

    for worker_component in worker worker-fanout worker-backfill; do
        worker_id="$(compose ps -q "${worker_component}")"
        [[ -n "${worker_id}" ]] || die "没有找到 ${worker_component} 容器"
        worker_state="$(docker inspect --format '{{.State.Status}}' "${worker_id}")"
        [[ "${worker_state}" == "running" ]] || {
            compose logs --tail=200 "${worker_component}"
            die "${worker_component} 未正常运行"
        }
    done

    auditor_id="$(compose ps -q auditor)"
    [[ -n "${auditor_id}" ]] || die "没有找到覆盖 Auditor 容器"
    auditor_state="$(docker inspect --format '{{.State.Status}}' "${auditor_id}")"
    [[ "${auditor_state}" == "running" ]] || {
        compose logs --tail=200 auditor
        die "覆盖 Auditor 未正常运行"
    }

    printf '\n'
    success "claw-quant-data 安装完成"
    printf '  Compose 项目：%s\n' "${PROJECT_NAME}"
    printf '  PostgreSQL：  localhost:%s/%s\n' \
        "$(read_env_value "DB_PORT")" "$(read_env_value "DB_NAME")"
    printf '  REST API：    http://localhost:%s\n' "$(read_env_value "API_PORT")"
    printf '  API 文档：    http://localhost:%s/api/docs\n' "$(read_env_value "API_PORT")"
    printf '  采集控制台：  http://localhost:%s/dashboard\n' "$(read_env_value "API_PORT")"
    printf '  初始采集：    请在采集控制台选择范围后单独启动\n'
    printf '  日常 Worker： running\n'
    printf '  扇出 Worker： running\n'
    printf '  回填 Worker： running\n'
    printf '  覆盖 Auditor：running\n'
    printf '  数据表：      %s\n' "${table_count}"
    printf '  查看状态：    docker compose -p %s ps\n' "${PROJECT_NAME}"
    printf '  查看日志：    docker compose -p %s logs -f scheduler\n' "${PROJECT_NAME}"
}

main
