#!/usr/bin/env python3
"""Inventory every declared capability and audit task coverage without provider calls.

Fresh checks cover a bounded recent window. Historical evidence retains its own
rule revision and audited bounds; neither a successful run nor a recent complete
window is presented as proof of complete history. All database sessions are read
only and queries have a statement timeout.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql

from service.clock import business_now
from service.config import DB_CONFIG
from service.data_coverage.calculator import CoverageCalculator, completed_quarters
from service.data_coverage.diagnostics import audit_issues
from service.data_coverage.registry import COVERAGE_RULES
from service.data_coverage.repository import CoverageRepository
from service.orchestration_v2.automation_status import task_automation
from service.orchestration_v2.catalog import acquisition_task_blueprints
from service.orchestration_v2.scheduling import _routine_scope
from service.source_connectors.ant_scheduled import SCHEDULED_ROUTES
from service.source_connectors.financial_data_catalog import FINANCIAL_DATA_ROUTES
from service.source_connectors.registry import SOURCE_REGISTRY
from service.tushare_catalog import TushareInterfaceCatalog
from scripts.audit_task_contracts import inventory


SENSITIVE_KEY = re.compile(r"token|password|authorization|cookie|secret|api_key|credential", re.I)
TOKEN_VALUE = re.compile(r"\b[0-9a-fA-F]{56}\b")


def sanitized(value):
    if isinstance(value, dict):
        return {str(k): sanitized(v) for k, v in value.items() if not SENSITIVE_KEY.search(str(k))}
    if isinstance(value, (list, tuple)):
        return [sanitized(v) for v in value]
    if isinstance(value, str):
        return TOKEN_VALUE.sub("[REDACTED]", value)
    return value


class ReadOnlyCoverageRepository(CoverageRepository):
    def __init__(self, timeout_ms=8000):
        self.timeout_ms = int(timeout_ms)

    @contextmanager
    def _connection(self):
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=5,
            application_name="claw-capability-review",
            options=f"-c statement_timeout={self.timeout_ms}")
        conn.set_session(readonly=True, autocommit=True)
        try:
            yield conn
        finally:
            conn.close()


def select_scope(rule, as_of, days=30, latest=None, cadence="daily"):
    """Respect business periods instead of inventing daily snapshot obligations."""
    today = as_of.date()
    if rule.strategy.value == "non_temporal":
        if cadence in {"weekly", "monthly", "quarterly"}:
            _, start, end, _ = _routine_scope(cadence, today)
            return start, end
        if latest and latest.get("observation_start") and latest.get("observation_end"):
            return latest["observation_start"], latest["observation_end"]
        return today - timedelta(days=1), today - timedelta(days=1)
    if rule.strategy.value.endswith("monthly"):
        _, start, end, _ = _routine_scope("monthly", today - timedelta(days=rule.grace_days))
        return start, end
    if rule.strategy.value == "report_quarterly":
        periods = completed_quarters(date(today.year - 2, 1, 1), today, today)
        end = periods[-1]
        return date(end.year, end.month - 2, 1), end
    end = _routine_scope(cadence, today)[2] if cadence in {"weekly", "monthly", "quarterly"} else today
    return max(end - timedelta(days=days - 1), rule.availability_start or date.min), end


def metadata(repository):
    queries = {
        "definitions": """SELECT DISTINCT ON (task_key) task_key,workflow_kind,lifecycle_status,
            version,definition FROM orchestration_v2.task_definition
            ORDER BY task_key,CASE lifecycle_status WHEN 'active' THEN 0 WHEN 'draft' THEN 1 ELSE 2 END,version DESC""",
        "latest_executions": """SELECT DISTINCT ON(task_key) task_key,task_execution_id,status,purpose,
            observation_start,observation_end,observation_key,final_error_category,final_error_message,
            final_error_detail,updated_at FROM orchestration_v2.task_execution
            WHERE status NOT IN ('cancelled','superseded') ORDER BY task_key,task_execution_id DESC""",
        "latest_attempts": """SELECT DISTINCT ON(task_key) task_key,task_execution_id,status,purpose,
            observation_start,observation_end,observation_key,definition_version,
            final_error_category,final_error_message,updated_at
            FROM orchestration_v2.task_execution ORDER BY task_key,task_execution_id DESC""",
        "pending": """SELECT task_key,status,purpose,count(*) AS executions,
            min(observation_start) AS start_date,max(observation_end) AS end_date,
            min(eligible_at) AS next_eligible FROM orchestration_v2.task_execution
            WHERE status IN ('created','queued','running','waiting_dependency','retrying','validating','publishing')
            GROUP BY task_key,status,purpose""",
        "history_requests": """SELECT task_key,min(observation_start) AS start_date,
            max(observation_end) AS end_date,count(*) AS executions
            FROM orchestration_v2.task_execution
            WHERE purpose IN ('backfill','initialization','repair') AND status NOT IN ('cancelled','superseded')
            GROUP BY task_key""",
        "heartbeats": """SELECT component,instance_id,last_seen_at,
            details->'resource_classes' AS resource_classes,details->'short_only' AS short_only
            FROM sys_service_heartbeat WHERE last_seen_at>=now()-interval '2 minutes'""",
        "execution_status_24h": """SELECT status,count(*) AS executions
            FROM orchestration_v2.task_execution WHERE created_at>=now()-interval '24 hours' GROUP BY status""",
        "latest_states": """SELECT DISTINCT ON(s.dataset_name) s.dataset_name,s.ready,s.data_status,
            s.observation_start,s.observation_end,s.contract_version,s.expected_count,s.actual_count,
            s.source_execution_id,e.status AS producer_status,s.updated_at
            FROM orchestration_v2.dataset_state s JOIN orchestration_v2.task_execution e
              ON e.task_execution_id=s.source_execution_id
            WHERE e.status NOT IN ('cancelled','superseded')
            ORDER BY s.dataset_name,s.observation_end DESC,s.updated_at DESC""",
    }
    result = {}
    with repository._connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cursor:
        for name, query in queries.items():
            cursor.execute(query)
            result[name] = [dict(row) for row in cursor.fetchall()]
    return result


def capabilities(records):
    links = defaultdict(list)
    task_records = {r["task_key"]: r for r in records}
    for blueprint in acquisition_task_blueprints():
        for endpoint in blueprint.endpoints:
            links[(endpoint.source_id, endpoint.endpoint_key)].append(blueprint.task_key)
    rows = []

    def add(source, key, title, tasks=(), **extra):
        tasks = sorted(tasks)
        rows.append({"source": source, "interface": key, "title": title,
            "task_keys": tasks,
            "published_tasks": [t for t in tasks if task_records[t]["published"]],
            "automatic_tasks": [t for t in tasks if task_records[t]["automation"]["automatic"]], **extra})

    for contract in TushareInterfaceCatalog().list():
        add("tushare", contract.api_name, contract.title,
            links[("tushare", contract.api_name)], declared_collectable=contract.collectable,
            permission=dict(contract.permission), implementation=dict(contract.implementation),
            mode="scheduled_pull" if contract.collectable else "catalogued_unavailable")
    route_keys = {spec.route: key for key, spec in SCHEDULED_ROUTES.items()}
    intraday = {"/api/v1/quote/basic-snapshot", "/api/v1/quote/kline-batch",
                "/api/v1/quote/capital-flow-range", "/api/v1/sector/plate-list"}
    for route in sorted(FINANCIAL_DATA_ROUTES):
        key = route_keys.get(route)
        add("financial_data", route, route, links[("financial_data", key)] if key else (),
            declared_collectable=True, mode="query_through", scheduled_endpoint=key,
            intraday_consumer=route in intraday,
            verification="allowlisted protocol capability; current provider availability not re-probed")
    for source in SOURCE_REGISTRY.list_sources():
        if source.source_id in {"tushare", "financial_data"}:
            continue
        for endpoint in SOURCE_REGISTRY.list_endpoints(source.source_id):
            add(source.source_id, endpoint.endpoint_key, endpoint.title,
                links[(source.source_id, endpoint.endpoint_key)], declared_collectable=True,
                mode=endpoint.acquisition_mode.value)
    return rows


def fresh_probe(repository, output, record, as_of, days, exact_scope=None):
    started = time.monotonic()
    rule = COVERAGE_RULES.get(output["dataset"])
    start, end = exact_scope or select_scope(rule, as_of, days, record.get("latest_execution"), record["cadence"])
    probe = {"start": start, "end": end, "observed_at": business_now(), "rule_revision": rule.revision}
    try:
        result = CoverageCalculator(repository).audit(rule, start, end, as_of=as_of)
        issues = audit_issues(result)
        probe.update({"status": ("no_mature_expected_period" if result.expected_partitions == 0
            and rule.detects_missing_partitions else result.status), "expected": result.expected_partitions,
            "present": result.present_partitions, "missing": result.missing_partitions,
            "partial": result.partial_partitions,
            "issue_counts": dict(Counter(i["code"] for i in issues)), "issue_examples": issues[:12],
            "partitions": [asdict(p) for p in result.partitions],
            "evidence": {k: v for k, v in result.evidence.items() if k in {
                "strict_audit_mode", "calendar_complete_for_range", "require_transport_proof",
                "verified_transport", "verified_empty", "row_count", "active_history_jobs",
                "unresolved_failures", "empty_reason", "empty_confirmed_after_window",
                "verified_empty_partitions", "before_release", "absence_detection"}}})
    except psycopg2.errors.QueryCanceled:
        probe.update(status="verification_timeout", reason="query timeout; no completeness claim")
    except Exception as exc:
        probe.update(status="verification_error", reason=type(exc).__name__)
    probe["seconds"] = round(time.monotonic() - started, 3)
    return probe


def daily_chunk_probe(repository, output, record, as_of, days):
    """Bound each scan without treating a timed-out query as missing data."""
    rule = COVERAGE_RULES.get(output['dataset'])
    start, end = select_scope(rule, as_of, days, record.get('latest_execution'), record['cadence'])
    chunks = [fresh_probe(repository, output, record, as_of, days, (day, day))
              for day in (start+timedelta(days=i) for i in range((end-start).days+1))]
    failed = [p for p in chunks if p['status'] in {'verification_timeout','verification_error'}]
    counts = {name: sum(p.get(name, 0) for p in chunks) for name in ('expected','present','missing','partial')}
    statuses = {p['status'] for p in chunks}
    status = ('verification_incomplete' if failed else 'gaps' if counts['missing'] or counts['partial']
              else 'unverified' if 'unverified' in statuses else 'no_mature_expected_period' if not counts['expected']
              else 'empty' if statuses <= {'empty','no_mature_expected_period'} else 'complete')
    issues = Counter()
    for chunk in chunks: issues.update(chunk.get('issue_counts', {}))
    return {'start': start, 'end': end, 'observed_at': business_now(), 'rule_revision': rule.revision,
            'method': 'one_calendar_day_per_query', 'status': status, **counts,
            'issue_counts': dict(issues), 'issue_examples': [i for p in chunks for i in p.get('issue_examples',[])][:12],
            'partitions': [part for p in chunks for part in p.get('partitions',[])],
            'failed_scans': [{'start': p['start'], 'status': p['status']} for p in failed],
            'seconds': round(sum(p['seconds'] for p in chunks), 3)}


def derived_history(repository, records, as_of):
    """Compare every mature contract period with physical rows and certificates.

    Reading date/metadata columns is not a historical numerical recomputation.
    Current-rule certificates remain a separate, explicitly named measure.
    """
    result = {}
    with repository._connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cursor:
        for record in records:
            if record['kind'] != 'transformation' or not record['published']:
                continue
            for output in record['outputs']:
                rule = COVERAGE_RULES.get(output['dataset'])
                start = rule.availability_start
                end = as_of.date() - timedelta(days=rule.grace_days)
                if start is None:
                    result[rule.dataset_name] = {'status': 'historical_start_not_declared'}
                    continue
                date_expr = CoverageRepository._date_expression(rule)
                cursor.execute(sql.SQL('SELECT {} AS period,count(*) AS rows FROM {} '
                    'WHERE {} BETWEEN %s AND %s GROUP BY 1 ORDER BY 1').format(
                    date_expr, sql.Identifier(rule.table), date_expr), (start, end))
                physical = {r['period']: r['rows'] for r in cursor.fetchall()}
                if rule.strategy.value.endswith('monthly'):
                    from service.data_coverage.calculator import completed_months
                    expected = set(completed_months(start, end, end))
                    calendar_complete = True
                else:
                    cursor.execute('SELECT cal_date,is_open FROM trade_cal WHERE exchange=%s '
                                   'AND cal_date BETWEEN %s AND %s', (rule.calendar_exchange, start, end))
                    calendar = list(cursor.fetchall())
                    calendar_complete = len({r['cal_date'] for r in calendar}) == (end-start).days+1
                    expected = {r['cal_date'] for r in calendar if r['is_open'] == 1}
                cursor.execute("""SELECT p.partition_date,p.status
                    FROM sys_data_coverage_partition p JOIN sys_data_coverage_audit a USING(audit_id)
                    WHERE p.dataset_name=%s AND p.partition_date BETWEEN %s AND %s
                      AND coalesce(nullif(a.evidence->>'rule_revision',''),'0')::int=%s""",
                    (rule.dataset_name, start, end, rule.revision))
                certified = {r['partition_date'] for r in cursor.fetchall() if r['status']=='present'}
                actual = expected & physical.keys()
                cursor.execute("""SELECT DISTINCT ON(observation_end) observation_end,status,
                    task_execution_id,final_error_category,final_error_message
                    FROM orchestration_v2.task_execution WHERE task_key=%s
                    AND observation_end BETWEEN %s AND %s
                    AND status NOT IN ('cancelled','superseded')
                    ORDER BY observation_end,task_execution_id DESC""", (record['task_key'],start,end))
                requests = {r['observation_end']: dict(r) for r in cursor.fetchall()}
                reasons = []
                if expected - physical.keys(): reasons.append('materialization_not_done_for_contract_periods')
                if actual - certified: reasons.append('current_rule_validation_missing_or_failed')
                row = {'contract_start': start, 'mature_end': max(expected) if expected else end,
                    'evaluation_cutoff': end, 'unit': 'month' if rule.strategy.value.endswith('monthly') else 'trading_day',
                    'calendar_complete': calendar_complete, 'expected_periods': len(expected),
                    'physical_periods': len(actual), 'physical_missing': len(expected-physical.keys()),
                    'current_rule_certified_periods': len(certified & expected),
                    'uncertified_existing_periods': len(actual-certified),
                    'physical_start': min(physical) if physical else None,
                    'physical_end': max(physical) if physical else None,
                    'missing_examples': sorted(expected-physical.keys())[:10],
                    'uncertified_examples': sorted(actual-certified)[:10],
                    'missing_periods': sorted(expected-physical.keys()),
                    'missing_request_status_counts': dict(Counter(
                        requests.get(day, {}).get('status','not_requested') for day in expected-physical.keys())),
                    'uncertified_request_status_counts': dict(Counter(
                        requests.get(day, {}).get('status','not_requested') for day in actual-certified)),
                    'latest_period_executions': list(requests.values()),
                    'reasons': reasons, 'rule_revision': rule.revision,
                    'status': 'complete' if calendar_complete and expected and expected<=certified and expected<=physical.keys() else 'incomplete_or_unverified'}
                if any(name=='formula_version' for name, value in rule.required_values):
                    cursor.execute(sql.SQL('SELECT formula_version,count(*) AS periods FROM {} '
                        'WHERE {} BETWEEN %s AND %s GROUP BY formula_version').format(sql.Identifier(rule.table),date_expr),(start,end))
                    row['stored_formula_versions'] = [dict(r) for r in cursor.fetchall()]
                result[rule.dataset_name] = row
        from service.research.local_factors.catalog import FACTOR_SCHEMA_VERSION
        cursor.execute("""SELECT issues.key AS factor,issues.value AS reason,count(*) AS securities
            FROM local_factor_snapshot f CROSS JOIN LATERAL jsonb_each_text(f.audit_evidence->'unresolved') issues
            WHERE f.schema_version=%s AND f.trade_date=(SELECT max(trade_date) FROM local_factor_snapshot WHERE schema_version=%s)
            GROUP BY 1,2 ORDER BY 3 DESC""", (FACTOR_SCHEMA_VERSION, FACTOR_SCHEMA_VERSION))
        result['local_factor_input_issues'] = [dict(r) for r in cursor.fetchall()]
        categories = Counter()
        for item in result['local_factor_input_issues']:
            reason = item['reason']
            category = ('waiting_for_inputs' if reason.startswith(('missing_financial_inputs:', 'missing_market_inputs:'))
                else 'invalid_or_conflicting_inputs' if reason.startswith(('invalid_market_inputs:', 'conflicting_financial_inputs:'))
                else 'calculation_guard' if reason in {'numerically_unstable_extreme_value', 'undefined_formula_domain_with_complete_market_window', 'alpha101_result_requires_formula_input_review'}
                else 'needs_review')
            item['category'] = category
            categories[category] += item['securities']
        result['local_factor_issue_counts'] = {'unresolved_security_factor_pairs': dict(categories),
            'notice': 'Counts are security/factor pairs; a security can appear in multiple causes.'}
    return result


def render_markdown(report):
    stats = report['summary']
    lines = ['# 采集与派生能力核查', '', f"核查开始：{report['started_at']}；完成：{report.get('finished_at', '进行中')}。",
        '', '> 近期待检范围按任务周期选择；完整历史另按契约起点比较。表内有行、任务 success、当前规则通过是不同证据。权限按登记契约列出，本次没有逐接口消耗额度探测。', '',
        f"已登记业务接口 {stats['capabilities']}；对应常规采集与专项流程 {stats['acquisition_tasks']}；"
        f"采集自动入口分类 {stats['acquisition_automation']}。派生蓝图 {stats['derived_tasks']}，已发布 {stats['published_derived']}。", '',
        '## 采集能力与启用范围', '', '| 来源 | 业务接口 | 已映射任务 | 有自动入口 |', '|---|---:|---:|---:|']
    for source, count in stats['capabilities_by_source'].items():
        interfaces = [c for c in report['capabilities'] if c['source'] == source]
        lines.append(f"| {source} | {count} | {sum(bool(c['task_keys']) for c in interfaces)} | {sum(bool(c['automatic_tasks']) for c in interfaces)} |")
    for state, title in [('manual', '需明确范围后手动运行'), ('paused_policy', '按策略暂停新增自动采集')]:
        names = [r['task_key'] for r in report['tasks'] if r['kind']=='acquisition' and r['automation']['state']==state]
        lines += ['', f"{title}：" + '、'.join(f'`{name}`' for name in names) + '。']
    lines += ['', f"自动采集流程的近期产出状态：{stats['automatic_acquisition_output_status']}。",
        '', '`complete` 只覆盖表内检查范围；`unverified` 表示缺少足够请求/范围证据；'
        '`gaps` 表示已定位到缺分区、实体不足或现行规则不通过；`empty` 只表示相应审计结果为空，'
        '须结合契约的 verified-empty 证据判断，不推定上游没有数据。检查超时保留为未核实。'
        '控制面已通过的某个周期与更宽窗口未通过可以同时成立。历史范围与旧规则问题另见 '
        '[历史审计账本汇总](dataset_audit_latest.md)，不能用本次近30日检查替代全历史认证。', '',
        '## 派生数据完整周期', '', '| 产出 | 契约起点 | 截止 | 应有周期 | 有物理记录 | 当前规则通过 | 缺物理记录 |', '|---|---|---|---:|---:|---:|---:|']
    for name, item in report.get('derived_history', {}).items():
        if not isinstance(item, dict) or 'expected_periods' not in item: continue
        lines.append(f"| {name} | {item['contract_start']} | {item['mature_end']} | {item['expected_periods']} | {item['physical_periods']} | {item['current_rule_certified_periods']} | {item['physical_missing']} |")
    lines += ['', '周期统计按当前契约与成熟日历计算；当前规则通过列来自现行版本的分区证书，'
        '不代表本次重新计算了每个历史数值。`technical_factor_snapshot` 是同一因子任务的兼容视图。', '',
        '派生缺口分类：本地272因子与技术视图缺少早期物化周期；财务输入缺失、冲突及公式保护'
        '分别记录在 JSON 的 `derived_history.local_factor_input_issues`。Fama-French 和估值分位'
        '还存在旧公式历史，须使用当前公式重新计算并独立验收。港股通月汇总有物理行，'
        '但多数历史月份仍缺源数据完整证据或聚合值不一致，不能直接认证。', '',
        '| 产出 | 缺物理周期的最新任务状态 | 有数据但未认证周期的最新任务状态 |', '|---|---|---|']
    for name, item in report.get('derived_history', {}).items():
        if not isinstance(item,dict) or 'expected_periods' not in item: continue
        lines.append(f"| {name} | {item.get('missing_request_status_counts',{})} | {item.get('uncertified_request_status_counts',{})} |")
    lines += ['', '`not_requested` 表示现有执行账本没有该周期的有效请求，不推定供应商没有数据。'
        '原始历史导入、旧公式 success、现行规则 attention 分开统计。完整缺期列表在 JSON 中。', '',
        '尚未实现、没有投产计算入口的派生蓝图：' + '、'.join(
            f"`{r['task_key']}`" for r in report['tasks'] if r['kind']=='transformation' and not r['published']) + '。', '',
        ]
    if report.get('repairs'):
        lines += ['## 已修复和清理', '',
            '已修复旧定义被替代后仍占用例行幂等身份的问题；仅为明确的定义替换创建新版本实例，'
            '不恢复人工取消或策略停采。蚂蚁股本结构与自由流通股本的2026-W45实例 '
            '197405、197407已成功，受控产出范围均为11月2日至8日，且通过当前契约。', '',
            '研报按自然日覆盖周末，当日请求等待22:30最终发布时点；提前执行则保留检查点等待，'
            '不把尚未成熟的周期报成永久失败。已识别的旧提前失败按稳定身份补建最终发布实例。', '',
            '本次已清理的过期数据库记录：' + str(report.get('cleanup',{}).get('database',{})) + '。'
            '旧报告与临时构建文件归档并校验共' + str(len(report.get('cleanup',{}).get('archived_artifacts',[]))) +
            '项；历史验收参考改名明确标记。每日保留策略见 [数据来源文档](../docs/DATA_SOURCES.md#原始证据与缓存)。', '']
    lines += ['## 每项任务与近期范围', '', '| 任务 | 类型 | 自动入口 | 检查范围 | 产出及状态 | 最近受控产出范围 | 原因 |', '|---|---|---|---|---|---|---|']
    for record in report['tasks']:
        for output in record['outputs']:
            fresh = output.get('fresh', {})
            scope = f"{fresh.get('start', '—')}..{fresh.get('end', '—')}"
            reasons = ', '.join(fresh.get('issue_counts', {})) or fresh.get('reason', '')
            state = output.get('latest_controlled_scope') or {}
            controlled = (f"{state['observation_start']}..{state['observation_end']}: {state['data_status']}"
                          if state else '无受控产出')
            lines.append(f"| {record['task_key']} | {record['kind']} | {record['automation']['state']} | {scope} | {output['dataset']}: {fresh.get('status','not_checked')} | {controlled} | {reasons} |")
    lines += ['', '## 接口到任务的完整映射', '', '| 来源 | 接口 | 任务 | 有自动入口的任务 | 模式 |', '|---|---|---|---|---|']
    for item in report['capabilities']:
        lines.append(f"| {item['source']} | {item['interface']} | {', '.join(item['task_keys']) or '无定时任务'} | {', '.join(item['automatic_tasks']) or '—'} | {item['mode']} |")
    return '\n'.join(lines) + '\n'


def summary(report):
    records = report["tasks"]
    acq = [r for r in records if r["kind"] == "acquisition"]
    derived = [r for r in records if r["kind"] == "transformation"]
    return {
        "capabilities": len(report["capabilities"]),
        "capabilities_by_source": dict(Counter(c["source"] for c in report["capabilities"])),
        "capabilities_with_task": sum(bool(c["task_keys"]) for c in report["capabilities"]),
        "capabilities_with_automatic_task": sum(bool(c["automatic_tasks"]) for c in report["capabilities"]),
        "acquisition_tasks": len(acq), "published_acquisitions": sum(r["published"] for r in acq),
        "acquisition_automation": dict(Counter(r["automation"]["state"] for r in acq)),
        "derived_tasks": len(derived), "published_derived": sum(r["published"] for r in derived),
        "fresh_output_status": dict(Counter(o.get("fresh", {}).get("status", "not_checked")
            for r in records for o in r["outputs"])),
        "automatic_acquisition_output_status": dict(Counter(o.get("fresh", {}).get("status", "not_checked")
            for r in acq if r["automation"]["automatic"] for o in r["outputs"])),
    }


def write_report(report, path):
    report["summary"] = summary(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(sanitized(report), ensure_ascii=False, indent=2, default=str) + "\n")
    temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/capability_coverage_latest.json")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--workers", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--timeout-ms", type=int, default=8000)
    parser.add_argument("--inventory-only", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.days <= 366 or not 1000 <= args.timeout_ms <= 60000:
        parser.error("days must be 1..366 and timeout-ms 1000..60000")
    as_of = business_now()
    repository = ReadOnlyCoverageRepository(args.timeout_ms)
    live = metadata(repository)
    definitions = {d["task_key"]: d for d in live["definitions"]}
    active_keys = {k for k, d in definitions.items() if d["lifecycle_status"] == "active"}
    executions = {e["task_key"]: e for e in live["latest_executions"]}
    attempts = {e["task_key"]: e for e in live["latest_attempts"]}
    history = {e["task_key"]: e for e in live["history_requests"]}
    states = {s['dataset_name']: s for s in live['latest_states']}
    ledger = repository.latest_audits()
    records = inventory()
    for record in records:
        key = record["task_key"]
        definition = definitions.get(key)
        record["published"] = key in active_keys
        record["lifecycle"] = definition["lifecycle_status"] if definition else "not_registered"
        document = definition["definition"] if record["published"] else None
        record["automation"] = task_automation(key, document, active_keys)
        record["scope_contract"] = (document or {}).get("scope_contract")
        record["schedule"] = (document or {}).get("schedule")
        record["latest_execution"] = executions.get(key)
        record["latest_attempt_including_replaced"] = attempts.get(key)
        record["historical_requests"] = history.get(key)
        record["pending"] = [p for p in live["pending"] if p["task_key"] == key]
        for output in record["outputs"]:
            output['latest_controlled_scope'] = states.get(output['dataset'])
            raw = ledger.get(output["dataset"])
            if raw:
                output["historical_audit"] = {k: v for k, v in raw.items() if k != "evidence"}
            if not record["published"]:
                output["fresh"] = {"status": "draft_not_implemented"}
            elif not output.get("rule"):
                output["fresh"] = {"status": "sample_manifest_only", "whole_market_certified": False}
    report = {"started_at": as_of, "code_base_revision": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "inventory_snapshot_digest": hashlib.sha256(json.dumps(records, default=str, sort_keys=True).encode()).hexdigest(),
        "code_worktree_dirty": bool(subprocess.check_output(['git','status','--porcelain'], cwd=ROOT)),
        "scope_notice": "Read-only inventory plus bounded fresh probes and separately versioned historical evidence. No provider requests or automatic repairs. No claim of complete history from a recent successful window.",
        "workers": args.workers, "recent_window_days": args.days,
        "runtime_heartbeats": live["heartbeats"], "execution_status_24h": live["execution_status_24h"],
        "tasks": records}
    report["capabilities"] = capabilities(records)
    report['derived_history'] = derived_history(repository, records, as_of)
    write_report(report, args.output)
    if not args.inventory_only:
        work = [(r, o) for r in records if r["published"] for o in r["outputs"] if o.get("rule")]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            jobs = {pool.submit(fresh_probe, repository, o, r, as_of, args.days): (r, o) for r, o in work}
            for number, future in enumerate(as_completed(jobs), 1):
                record, output = jobs[future]
                output["fresh"] = future.result()
                if number % 10 == 0 or number == len(work):
                    write_report(report, args.output)
                    print(f"{number}/{len(work)} outputs checked", flush=True)
        timed_out = [(r,o) for r,o in work if o.get('fresh',{}).get('status')=='verification_timeout'
                     and COVERAGE_RULES.get(o['dataset']).strategy.value in {'trading_daily','calendar_daily'}]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            jobs = {pool.submit(daily_chunk_probe,repository,o,r,as_of,args.days):(r,o) for r,o in timed_out}
            for future in as_completed(jobs):
                record, output = jobs[future]
                output['wide_query_timeout'] = output['fresh']
                output['fresh'] = future.result()
                write_report(report,args.output)
                print(f"daily chunks checked {record['task_key']}/{output['dataset']}",flush=True)
    report["finished_at"] = business_now()
    write_report(report, args.output)
    args.output.with_suffix('.md').write_text(render_markdown(sanitized(report)), encoding='utf-8')
    print(json.dumps(report["summary"], ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
