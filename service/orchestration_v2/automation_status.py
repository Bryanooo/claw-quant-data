"""Code-owned supplementary triggers; registration is not automation."""

WEEKLY_REFERENCE_PROFILES = {
    'fund_basic': ({'market': 'E'}, {'market': 'O'}),
    'fut_basic': tuple({'exchange': exchange} for exchange in
                       ('CFFEX', 'DCE', 'CZCE', 'SHFE', 'INE', 'GFEX')),
    'index_member_all': ({'is_new': 'Y'},),
    'ci_index_member': ({'is_new': 'Y'},),
}

FINANCIAL_ROLLING_REFRESH_TASKS = (
    'income', 'balancesheet', 'cashflow', 'financial_indicator',
)

MANUAL_REASONS = {
    'bc_otcqt': '柜台实时行情：尚未定义监测证券与时段',
    'cb_rate': '转债条款：需冻结转债代码范围和变更巡检周期',
    'cb_rating': '转债评级：需冻结转债代码范围和变更巡检周期',
    'cb_share': '转股事件：需代码及公告日期窗口',
    'ccass_hold_detail': '港股持仓明细：需证券范围与调用预算',
    'dc_concept_cons': '概念成员：需有界股票范围及完整性验收',
    'express': '业绩快报：尚未接入披露滚动刷新，待补自动编排',
    'fina_audit': '审计意见：需年度报告期及证券范围',
    'fina_mainbz': '主营构成：需报告期、产品/地区类型和请求预算',
    'fut_holding': '期货持仓：需交易所/合约范围',
    'fut_index_daily': '期货指数：需核验指数全集和每日参数',
    'fut_weekly_monthly': '期货周期行情：需分别指定周/月及交易所范围',
    'p_get': '自选组合查询，不是市场数据定时采集',
    'pledge_stat': '质押统计：尚未配置最新截止日巡检，待补自动编排',
    'rt_hk_k': '港股实时K线：需盘中证券范围与额度预算',
    'stk_mins': '分钟历史：需证券、频率及时间窗口，禁止全市场无界采集',
    'stk_rewards': '高管薪酬：需年度报告期，待补年度滚动编排',
    'stk_week_month_adj': '复权周期行情：需分别指定周/月和日期口径',
    'stk_weekly_monthly': '周期行情：需分别指定周/月和日期口径',
    'stock_hsgt': '沪深港通名单：需明确类型分区，待补定期刷新',
    'tdx_member': '通达信成员：需板块全集、日期及分页验收',
    'top10_cb_holders': '转债持有人：需转债代码与报告期范围',
}


def supplementary_automation(task_key, active_keys=()) -> dict | None:
    """Describe the code-owned trigger that still dispatches this task.

    Some tasks are deliberately driven from code rather than from their own
    schedule: their definition stays ``disabled`` so the generic routine
    dispatcher skips them, while a bounded code trigger does the real work.
    That is a legitimate pattern, but it is invisible in the control plane
    unless the reason is stated here — and this function is the single place
    that states it, so the console and the consistency audit cannot disagree.
    """

    if task_key in FINANCIAL_ROLLING_REFRESH_TASKS:
        return {'label': '每日18:20最近两报告期滚动刷新'}
    if task_key in WEEKLY_REFERENCE_PROFILES:
        return {'label': '有界周刷新（本周首次巡检）'}
    if task_key == 'factor_reference_sample':
        return {'label': '15分钟巡检：本地快照就绪后有界抽样（受额度限制）'}
    if task_key == 'index_weight' and 'valuation_percentile_snapshot' in active_keys:
        return {'label': '月度依赖刷新：仅沪深300、科创50',
                'scope': ['000300.SH', '000688.SH']}
    return None


def task_automation(task_key, definition, active_keys):
    if definition is None:
        return {'state': 'not_published', 'label': '无已发布任务', 'automatic': False}
    mode = (definition.get('schedule') or {}).get('mode', 'unknown')
    if task_key in {'factor_value', 'us_daily'}:
        label = ('全市场采集停用；仅独立抽样参考任务' if task_key == 'factor_value'
                 else '策略停采：额度与范围限制')
        return {'state': 'paused_policy', 'label': label, 'automatic': False}
    supplementary = supplementary_automation(task_key, active_keys)
    if supplementary is not None:
        return {'state': 'supplementary', 'automatic': True, **supplementary}
    if mode in ('cron', 'dependency'):
        return {'state': mode, 'label': '定时派发已配置' if mode == 'cron' else '依赖就绪触发', 'automatic': True}
    return {'state': 'manual', 'label': '未配置自动入口', 'automatic': False,
            'reason': MANUAL_REASONS.get(task_key, '需明确范围、参数及验收策略')}
