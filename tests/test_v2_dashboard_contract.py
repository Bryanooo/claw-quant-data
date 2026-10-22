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
    assert "当前数据缺口和仍需处理的执行异常" in html
    assert "历史尝试不计入问题数" in html
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
    assert "数据源总览" in html
    assert "servicePrev" in html and "serviceNext" in html
    assert 'api("/api/v1/catalog")' in script
    assert "local_datasets" in script
    assert "供应商、连接器和权限映射已从本目录移到“数据依赖”" in script


def test_dashboard_exposes_financial_data_dependency_matrix():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert "接口依赖明细" in html
    assert "蚂蚁必需" in script
    assert "/api/v1/data/dependencies/interfaces" in script
    assert "equivalence_class" in script


def test_dashboard_exposes_financial_data_real_usage_and_research_scope():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert "蚂蚁 实际调用" in html
    assert "状态按批次统计" in html
    assert 'id="financialResearchCount"' in html
    assert "/api/v1/data/sources/ant_data/usage?limit=20" in script
    assert "research_integration" in script
    assert 'u.latest_status==="failed"' in script
    assert "failed_last_24h" in script


def test_dashboard_starts_with_one_machine_readable_system_overview():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert "系统全貌与唯一口径" in html
    assert 'const system = await api("/api/v1/system/overview")' in script
    assert "system.runtime.summary" in script
    assert 'id="systemNumberDefinitions"' in html
    assert 'id="systemBoundaries"' in html
    assert "system.number_definitions" in script
    assert "system.boundaries" in script


def test_data_dependency_page_has_provider_and_supply_strategy_hierarchy():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    css = (ROOT / "service/dashboard/dashboard.css").read_text()
    assert "数据源总览" in html
    assert "接口依赖明细" in html
    assert 'id="interfaceRows"' in html
    assert 'id="fieldLineageView"' in html
    assert 'id="lineageRows"' in html
    assert "状态色约定" in html
    assert "联动跳转" in html
    assert "/api/v1/data/dependencies/interfaces" in script
    assert "/api/v1/data/dependencies/field-lineage" in script
    assert "/api/v1/data/dependencies/summary" in script
    assert "page_size=200" in script
    assert "strip-tile" in script
    assert "interfaceDetailParts" in script
    assert "equivalenceLabels" in script
    assert "不落业务表" in script
    assert "仅请求证据" in script
    assert "data-goto-service" in script
    assert "data-goto-coverage" in script
    assert ".source-mapping-table" in css
    assert ".interface-detail-row" in css
    assert ".lineage-field" in css
    assert ".source-strip" in css
    assert ".pill.info" in css
    assert ".legend-box" in css


def test_dashboard_has_stock_search_and_audited_multiframe_factor_charts():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    css = (ROOT / "service/dashboard/dashboard.css").read_text()

    assert 'data-view="stock"' in html
    assert 'id="stockSearch"' in html
    assert 'id="stockPriceChart"' in html
    assert 'id="stockVolumeChart"' in html
    assert 'id="stockMacdChart"' in html
    assert 'id="stockWatchlist"' in html
    assert 'id="stockWatchToggle"' in html
    assert "牛门线与确认线按交易日定义" in html
    # 个股研究升级：研究模块页签（行情因子/筹码/基本面/事件/板块/产业链，懒加载）
    assert 'id="stockModuleTabs"' in html
    for module in ("market", "chips", "fundamentals", "events", "sectors", "chain"):
        assert f'data-stock-module="{module}"' in html
        assert f'data-stock-module-panel="{module}"' in html
    assert "resetStockModules" in script
    assert "selectStockModule" in script
    assert 'industry-chain' in script
    # 数据依赖页：资产类型筛选独立列
    assert 'id="interfaceAssetClass"' in html
    assert "assetClassLabels" in script
    assert "<th>资产类型</th>" in html
    assert "asset-badge" in script
    assert ".asset-badge" in css
    assert "/api/v1/research/stocks/search" in script
    assert "/api/v1/research/watchlist" in script
    assert 'method:"POST"' in script
    assert 'method:"DELETE"' in script
    assert "/technicals?lookback_days=3000" in script
    assert "include_external=false" in script
    assert "macd_histogram" in script
    assert "niumen_confirmation_line" in script
    assert ".stock-factor-grid" in css
    assert ".stock-watchlist-card" in css


def test_stock_chart_supports_zoom_complete_tooltips_and_volume_units():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    css = (ROOT / "service/dashboard/dashboard.css").read_text()

    assert 'id="stockZoomIn"' in html
    assert 'id="stockZoomOut"' in html
    assert 'id="stockZoomReset"' in html
    assert 'id="stockPan"' in html
    assert 'id="stockPanPrev"' in html
    assert 'id="stockPanNext"' in html
    assert 'id="stockChartStage"' in html
    assert 'id="stockVolumeTitle"' in html
    assert "zoomStockChart" in script
    assert "panStockChart" in script
    assert "chart_points=1500" in script
    assert 'id="stockHistoryRange"' in html
    assert "完整历史" in script
    assert "setPointerCapture" in script
    assert 'addEventListener("wheel"' in script
    assert "stockActiveLines" in script
    assert "definition.label" in script
    assert "stockVolumeText" in script
    assert "亿手" in script and "万手" in script
    assert "ma_120" in script and "ma_250" in script
    assert "ema_12" in script and "ema_26" in script
    assert ".stock-zoom-controls" in css


def test_both_calendars_highlight_the_local_current_date():
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    css = (ROOT / "service/dashboard/dashboard.css").read_text()

    assert 'aria-current="date"' in script
    assert '" today"' in script
    assert ".day.today" in css
    assert ".day b em" in css
