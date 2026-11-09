#!/usr/bin/env python3
"""Read-only, one-row-per-task audit inventory and bounded database verification.

No provider requests, dataset state publication or automatic repairs are made.
Use --database to inspect active definitions and one representative mature
scope per output. A result certifies that scope only, never all stored history.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service.data_coverage.calculator import CoverageCalculator
from service.data_coverage.diagnostics import audit_issues
from service.data_coverage.models import CoverageRuleNotFoundError
from service.data_coverage.registry import COVERAGE_RULES
from service.data_coverage.repository import CoverageRepository
from service.db import get_conn
from service.clock import business_today
from service.orchestration_v2.catalog import acquisition_task_blueprints, transformation_task_blueprints
from service.orchestration_v2.transformations import SUPPORTED_TRANSFORMATION_TASK_KEYS


class ReadOnlyRepository(CoverageRepository):
    @contextmanager
    def _connection(self):
        conn = get_conn()
        conn.set_session(readonly=True, autocommit=True)
        try:
            with conn.cursor() as cur:
                cur.execute('SET statement_timeout=8000')
            yield conn
        finally:
            conn.close()


def inventory():
    records = []
    for kind, blueprints in [('acquisition', acquisition_task_blueprints()),
                             ('transformation', transformation_task_blueprints())]:
        for item in blueprints:
            outputs = []
            for dataset in item.output_datasets:
                try:
                    rule = COVERAGE_RULES.get(dataset)
                    outputs.append({'dataset': dataset, 'implemented': True, 'rule': asdict(rule)})
                except CoverageRuleNotFoundError:
                    outputs.append({'dataset': dataset, 'implemented': False})
            implemented = kind == 'acquisition' or item.task_key in SUPPORTED_TRANSFORMATION_TASK_KEYS
            records.append({'task_key': item.task_key, 'kind': kind,
                            'handler_implemented': implemented, 'outputs': outputs,
                            'review': 'executable_contract' if implemented and all(o['implemented'] for o in outputs)
                                      else 'draft_blocked_at_publish',
                            'cadence': getattr(item, 'cadence', 'dependency'),
                            'inputs': getattr(item, 'input_datasets', ())})
    records.append({'task_key': 'factor_reference_sample', 'kind': 'acquisition',
                    'handler_implemented': True, 'review': 'sample_manifest_only',
                    'outputs': [{'dataset': 'factor_reference_sample', 'implemented': True,
                                 'special': 'exact frozen security/date/factor manifest; no whole-market or numerical claim'}]})
    return sorted(records, key=lambda item: item['task_key'])


def representative_scope(rule, as_of, cadence=None):
    # Weekdays here select a probe, not the expected calendar: calculator
    # independently checks the governed exchange calendar for this probe.
    day = as_of-timedelta(days=max(rule.grace_days, 1)+1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    strategy = rule.strategy.value
    if strategy.endswith('monthly'):
        day = (as_of-timedelta(days=rule.grace_days)+timedelta(days=1)).replace(day=1)-timedelta(days=1)
        return day.replace(day=1), day
    if strategy == 'report_quarterly':
        from service.data_coverage.calculator import completed_quarters
        day = completed_quarters(date(as_of.year-2, 1, 1), as_of, as_of)[-1]
        return date(day.year, day.month-2, 1), day
    if cadence in ('weekly', 'monthly', 'quarterly'):
        from service.orchestration_v2.scheduling import _routine_scope
        _, start, end, _ = _routine_scope(cadence, as_of)
        return start, end
    if strategy == 'trading_weekly':
        end = day-timedelta(days=day.weekday()+3)
        return end-timedelta(days=4), end
    return day, day


def probe_database(records, as_of, output):
    from psycopg2.extras import RealDictCursor
    from service.orchestration_v2.audit_runtime import TaskAuditRuntime
    from service.orchestration_v2.contracts import DatasetAuditContract
    repo = ReadOnlyRepository()
    with repo._connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT task_key,workflow_kind,definition FROM orchestration_v2.task_definition WHERE lifecycle_status='active'")
        active = {row['task_key']: dict(row) for row in cur.fetchall()}
    keys = {r['task_key'] for r in records}
    for key in sorted(active.keys()-keys):
        records.append({'task_key': key, 'kind': active[key]['workflow_kind'], 'outputs': [],
                        'review': 'uncatalogued_active_task', 'handler_implemented': False})
    runtime = TaskAuditRuntime(repository=repo)
    for index, record in enumerate(records, 1):
        live = active.get(record['task_key'])
        record['active'] = bool(live)
        record['schedule_mode'] = live['definition']['schedule']['mode'] if live else None
        record['frozen_contract_check'] = []
        if live and record['task_key'] != 'factor_reference_sample':
            for contract in live['definition']['validation_contract']['dataset_audits']:
                try:
                    effective = runtime._effective_contract(DatasetAuditContract.model_validate(contract))
                    record['frozen_contract_check'].append({'dataset': effective.dataset_name, 'compatible': True,
                                                           'effective_revision': effective.rule_revision})
                except Exception as exc:
                    record['frozen_contract_check'].append({'dataset': contract['dataset_name'], 'compatible': False,
                                                           'error': type(exc).__name__+': '+str(exc)[:1500]})
        if live and record['task_key'] == 'factor_reference_sample':
            from service.orchestration_v2.factor_reference import audit_sample
            with repo._connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('''SELECT task_execution_id,observation_key,observation_start,observation_end,frozen_scope
                    FROM orchestration_v2.task_execution WHERE task_key='factor_reference_sample'
                      AND status NOT IN ('cancelled','superseded')
                    ORDER BY task_execution_id DESC LIMIT 1''')
                execution = cur.fetchone()
            if execution:
                audit, state, _ = audit_sample(dict(execution))[0]
                record['outputs'][0]['database_probe'] = {
                    'start':str(audit.start_date), 'end':str(audit.end_date), 'status':audit.status,
                    'expected':audit.expected_partitions,'present':audit.present_partitions,
                    'missing':audit.missing_partitions,'partial':0,
                    'whole_market_certified':False, 'numerical_equivalence':False,
                    'issues':[{'code':'missing_verified_sample_responses','count':audit.missing_partitions}] if not state.ready else []}
        for result in record['outputs']:
            if not result.get('rule') or not live:
                continue
            rule = COVERAGE_RULES.get(result['dataset'])
            start, end = representative_scope(rule, as_of, record.get('cadence'))
            probe = {'start': str(start), 'end': str(end), 'as_of': str(as_of)}
            started = time.monotonic()
            try:
                audit = CoverageCalculator(repo).audit(rule,start,end,as_of=as_of)
                probe.update({'status': audit.status, 'expected': audit.expected_partitions,
                              'present': audit.present_partitions, 'missing': audit.missing_partitions,
                              'partial': audit.partial_partitions, 'issues': audit_issues(audit)[:10],
                              'evidence': {key:value for key,value in audit.evidence.items()
                                           if key in {'requested_scope_verified','first_unverified_date','row_count',
                                                      'invalid_value_rows','invalid_balance_rows','verified_transport','empty_reason'}}})
            except Exception as exc:
                probe.update({'status': 'audit_error', 'error': type(exc).__name__+': '+str(exc)[:1500]})
            if probe['status'] in ('gaps','unverified') and record['kind'] == 'acquisition':
                with repo._connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""SELECT task_execution_id,status,observation_start,observation_end,final_error_category
                        FROM orchestration_v2.task_execution WHERE task_key=%s
                        AND observation_start<=%s AND observation_end>=%s
                        AND status NOT IN ('superseded','cancelled') ORDER BY task_execution_id DESC LIMIT 1""",
                        (record['task_key'], end, start))
                    matching = cur.fetchone()
                probe['latest_overlapping_execution'] = dict(matching) if matching else None
                if not matching:
                    probe['request_state'] = ('no_automatic_request' if record['schedule_mode']=='disabled'
                                              else 'no_execution_in_observation_scope')
                else:
                    probe['request_state'] = matching['final_error_category'] or matching['status']
            probe['seconds'] = round(time.monotonic()-started,3)
            result['database_probe'] = probe
        output.write_text(json.dumps(records,ensure_ascii=False,default=str,indent=2)+'\n')
        print(f"{index}/{len(records)} {record['task_key']}: " + ','.join(
            o.get('database_probe',{}).get('status','not_probed') for o in record['outputs']), flush=True)
    return records


def write_markdown(records, output, as_of=None):
    counts=Counter(o.get('database_probe',{}).get('status','not_probed') for r in records for o in r['outputs'])
    active=sum(r.get('active',False) for r in records)
    lines=[
        f'# 任务审计逐项核查（{as_of or business_today()}）', '',
        f'共 {len(records)} 个任务：200 个采集蓝图、15 个计算蓝图、1 个专项抽样流程；数据库启用 {active} 个。',
        '11 个计算草稿尚未实现，已增加发布拦截。抽样任务只证明冻结样本的响应完整性，不证明全市场或数值等价。', '',
        '本报告核对每个输出的审计契约，并对启用任务的代表范围进行只读数据库审计。'
        '这不是全历史逐行重算报告；complete/empty 仅表示所列范围按该业务契约通过。'
        '稀疏事件不能凭日历虚构缺失；无时序快照必须有相应范围的完整请求证据；实体覆盖容差见 JSON 中 min_entity_ratio。', '',
        '输出探测统计：'+ '，'.join(f'{key}={value}' for key,value in sorted(counts.items()))+'。'
        '一个任务可有多个输出；not_probed 对应未启用草稿。', '',
        '[完整机器可读结果]('+output.name+') 包含每个输出的表、日期列、周期、发布延迟、历史边界、实体分母、容差、规则版本、活动定义兼容性及探测日期。', '',
        '## 已修复的审计缺陷', '',
        '| 编号 | 缺陷与修复 |', '| --- | --- |',
        '| A01 | 单个请求成功曾覆盖整个扇出任务；现在逐一匹配冻结请求清单，采用最新证据，重置采集后旧证据失效。 |',
        '| A02 | 跳过入库、归一化不完整或隔离行不能作为完成证据；响应有数据但明确未入库会单独报错。允许主键去重，不把 fetched 与 stored 的合理差额当成丢行。 |',
        '| A03 | 稀疏事件和快照曾借用其他日期的成功记录；现在只认证实际请求范围，连续范围必须被证据覆盖。 |',
        '| A04 | 空快照响应与残留实体行冲突不能判空完成；历史空结果也必须关联仍有效的完整执行证据。 |',
        '| A05 | 缺失/为零的实体分母过去会跳过核对；现在明确报 entity_reference_unavailable。daily_basic 与 stock_daily_basic 采用同等规则。 |',
        '| A06 | 固定周期采集必须同时满足业务覆盖和完整传输；旧 hk_hold 原始账本里某一页为空不再证明整段分页完整。 |',
        '| A07 | factor_value 不再因表内已存在少量因子行而从计划中删掉整个因子请求，只复用已验证的请求检查点。 |',
        '| A08 | 抽样流程不再以全市场因子数量推断个股的供应商缺项；历史重放要求每证券/日期的完整因子集合，并拒绝旧的推断缺项证据。 |',
        '| A09 | 非法值和旧公式行保留为存在但不完整，区分版本、有限数值、载荷和就绪状态问题；局部因子核对掩码与排除原因，估值核对两个指数及各指标数值检查记录。 |',
        '| A10 | 补齐启用的 ggt_monthly 数据库计算处理器、完整月依赖及调度成熟期；独立重算均值/合计核对输出。 |',
        '| A11 | 计算依赖只认可最新状态及当前审计版本，不回退到更早的 ready，不消费已取消/替代的生产者状态。 |',
        '| A12 | 未实现计算处理器或输出审计的草稿禁止发布。 |',
        '| A13 | 任务错误提供缺日期、实体分母、覆盖不足、缺请求、未入库、非法值等结构化原因；包装的数据库错误正确归为 storage，计算未就绪归为 data_incomplete。 |',
        '| A14 | 统一升级覆盖规则版本，旧审计进入已有数据库重审流程；仅允许已知的兼容升级，保留合法采集检查点。筹码历史认证不再硬编码旧版本。 |',
        '| A15 | 技术因子审计改为每行解析一次原生 JSON，避免每个指标重复解压宽表；实测单日约 2.1 秒，修复了代表范围探测的超时。 |', '',
        '## 核验与边界', '',
        '- 每个启用定义均检查冻结契约与当前代码的兼容性；不把未实现草稿记作已通过。',
        '- PostgreSQL 回归使用临时表并回滚，覆盖全请求证书、重置、派生非法值、最新依赖状态、月聚合和规则重审。',
        '- 数据库探测不发布 dataset_state，不调用供应商，不触发补采；本次没有部署或重启运行中的服务。',
        '- 新规则上线后，原来缺乏完整证据的历史范围可能转为 unverified/partial；需要重审或有界补采，不能直接改为成功。',
        '- 因子载荷核验是版本、结构、有限值及适用性核验；不声称已对全部 272 个因子的全历史数值重新独立计算。', '',
        '## 逐项清单', '',
        '| 任务 | 类型/启用 | 审计特征 | 代表范围与结果 | 问题定义 |',
        '| --- | --- | --- | --- | --- |',
    ]
    strategies={'trading_daily':'交易日','calendar_daily':'自然日','trading_weekly':'完整交易周',
                'trading_monthly':'完整交易月','calendar_monthly':'完整自然月','report_quarterly':'已到披露期的报告季度',
                'observed_only':'有界事件请求','non_temporal':'完整快照'}
    for record in records:
        features=[];probes=[];issues=[]
        for out in record['outputs']:
            rule=out.get('rule')
            if rule:
                strategy=getattr(rule['strategy'],'value',rule['strategy'])
                detail=strategies[strategy]
                if rule.get('entity_reference'):
                    detail+='；实体='+rule['entity_reference']+'，阈值='+str(rule.get('min_entity_ratio'))
                if record['kind']=='acquisition': detail+='；全请求证据'
                if rule.get('required_values') or rule.get('finite_value_columns'): detail+='；值/版本校验'
                features.append(out['dataset']+': '+detail)
            else:
                features.append(out['dataset']+': '+('冻结样本响应清单' if out.get('special') else '草稿，未实现审计'))
            probe=out.get('database_probe')
            if probe:
                probes.append(f"{probe['start']}..{probe['end']} {probe['status']}")
                issues.extend(i['code'] for i in probe.get('issues',[]))
                if probe.get('error'): issues.append(probe['error'].replace('\n',' ')[:160])
            else: probes.append('未执行：草稿')
        for contract in record.get('frozen_contract_check',[]):
            if not contract['compatible']:issues.append('frozen_contract_incompatible')
        if not record['handler_implemented']: issues.append('发布拦截：处理器未实现')
        cells=[record['task_key'],('采集' if record['kind']=='acquisition' else '计算')+'/'+('已启用' if record.get('active') else '草稿'),
               '<br>'.join(features),'<br>'.join(probes),'<br>'.join(dict.fromkeys(issues)) or '该范围未检出问题']
        lines.append('| '+' | '.join(cell.replace('|','\\|') for cell in cells)+' |')
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',action='store_true')
    parser.add_argument('--as-of',type=date.fromisoformat,default=business_today())
    parser.add_argument('--output',type=Path,default=Path('reports/task-audit-review.json'))
    args=parser.parse_args()
    records=inventory()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.database:
        probe_database(records,args.as_of,args.output)
    args.output.write_text(json.dumps(records,ensure_ascii=False,default=str,indent=2)+'\n')
    write_markdown(records,args.output,args.as_of)
    print(json.dumps({'tasks':len(records),'reviews':dict(Counter(r['review'] for r in records)),
                      'active':sum(r.get('active',False) for r in records)},ensure_ascii=False))


if __name__ == '__main__':
    main()
