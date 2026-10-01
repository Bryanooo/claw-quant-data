from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_is_v2_only():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert "V2 Data Ops" in html
    assert "/api/v1/ops/orchestration-v2/executions" in script
    assert "/api/v1/ops/orchestration-v2/data-calendar" in script
    assert "collection-jobs" not in script
    assert "collection-fanout" not in script


def test_dashboard_distinguishes_task_and_data_state():
    html = (ROOT / "service/dashboard/index.html").read_text()
    assert "任务状态和数据状态分别核验" in html
    assert "日期是数据日期" in html


def test_dashboard_exposes_paginated_service_lineage():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert "服务能力与数据来源" in html
    assert "servicePrev" in html and "serviceNext" in html
    assert 'api("/api/v1/catalog")' in script
    assert "local_datasets" in script
    assert "fallback_routes" in script


def test_dashboard_exposes_financial_data_dependency_matrix():
    html = (ROOT / "service/dashboard/index.html").read_text()
    script = (ROOT / "service/dashboard/dashboard.js").read_text()
    assert "Financial Data ↔ Tushare 全量映射" in html
    assert "Tushare 公告解析" in html
    assert "Financial Data 必需" in html
    assert 'api("/api/v1/data/source-priorities")' in script
    assert "provider_equivalence_summary" in script
    assert "equivalence_class" in script
