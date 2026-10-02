from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_hides_engine_generation_from_operators():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert "V2" not in html
    assert "V2" not in script
    assert "/api/v1/ops/executions" in script
    assert "/api/v1/ops/coverage/calendar" in script
    assert "collection-jobs" not in script
    assert "collection-fanout" not in script


def test_dashboard_distinguishes_task_and_data_state():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert "任务状态和数据状态分别核验" in html
    assert "日期是业务数据日期" in html
    assert "采集任务" in html
    assert "执行历史" in html
    assert "查看节点" in script
    assert "查看任务定义与节点" in script


def test_dashboard_overview_uses_deduplicated_issue_semantics():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert "当前问题" in html
    assert "重复重试记录请到“执行历史”查看" in html
    assert "waiting_upstream" in script
    assert "attention_attempts" in script
    assert "尝试次数不再当作问题数" in script


def test_today_delivery_has_client_side_filter_and_pagination():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert 'id="todayStatus"' in html
    assert 'id="todayPrev"' in html and 'id="todayNext"' in html
    assert "renderTodayRows" in script
    assert "output_datasets" in script
    assert "日历型数据可能已由此前快照覆盖" in script
    assert "getFullYear" in script


def test_task_catalog_filters_by_cadence_and_shows_data_flow():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert 'id="taskCadence"' in html
    assert 'value="daily"' in html and 'value="weekly"' in html
    assert 'p.set("cadence"' in script
    assert "dataset-flow" in script
    assert "taskResultCount" in script


def test_execution_history_shows_total_count():
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert "view.page.total" in script
    assert "共 ${fmt(state.execution.total)} 条" in script


def test_investment_calendar_is_prominent_and_initialization_is_secondary():
    html = (ROOT / "service/dashboard/index.html").read_text()
    investment = html.index('data-view="investment"')
    governance = html.index('<p class="nav-group">治理</p>')
    assert investment < governance
    assert 'class="nav" data-view="initialization"' not in html
    assert 'data-view-target="initialization"' in html


def test_data_calendar_detail_is_actionable_and_paginated():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert 'id="calendarDetailStatus"' in html
    assert 'id="calendarDetailPrev"' in html
    assert 'id="calendarDetailNext"' in html
    assert "renderCalendarDetail" in script
    assert "查看采集证据" in script
    assert "状态来自数据证据而不是任务结果" in script


def test_dashboard_separates_public_services_from_internal_dependencies():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert "对外服务目录" in html
    assert "上游数据源" in html
    assert "servicePrev" in html and "serviceNext" in html
    assert 'api("/api/v1/catalog")' in script
    assert "local_datasets" in script
    assert "供应商、连接器和权限映射已从本目录移到“数据依赖”" in script


def test_dashboard_exposes_financial_data_dependency_matrix():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert "数据能力供给策略" in html
    assert "Tushare 公告解析" in html
    assert "Financial Data 必需" in html
    assert 'api("/api/v1/data/source-priorities")' in script
    assert "provider_equivalence_summary" in script
    assert "equivalence_class" in script


def test_data_dependency_page_has_provider_and_supply_strategy_hierarchy():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    css = (ROOT / "service/dashboard/dashboard.css").read_text()
    assert "上游数据源" in html
    assert "数据能力供给策略" in html
    assert 'class="strategy-grid"' in html
    assert 'data-source-class="tushare_direct"' in html
    assert 'data-source-class="financial_data_only"' in html
    assert "provider-card" in script
    assert "coverageLabels" in script
    assert ".source-mapping-table" in css
