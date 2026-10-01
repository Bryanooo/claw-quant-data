"""Representative end-to-end acceptance set for research services."""

from __future__ import annotations

from typing import Any


RESEARCH_VALIDATION_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "catl-fundamentals",
        "subject": "300750.SZ 宁德时代",
        "path": "/api/v1/research/stocks/300750.SZ/fundamentals?periods=12",
        "domains": ["stock_fundamental"],
        "required_paths": ["data.profile.ts_code", "data.periods", "meta.quality.status"],
        "minimum_lengths": {"data.periods": 4},
    },
    {
        "id": "catl-valuation",
        "subject": "300750.SZ 宁德时代",
        "path": "/api/v1/research/stocks/300750.SZ/valuation?lookback_days=730",
        "domains": ["stock_fundamental"],
        "required_paths": ["data.latest.trade_date", "data.historical_distribution", "meta.quality.status"],
    },
    {
        "id": "catl-technicals",
        "subject": "300750.SZ 宁德时代",
        "path": "/api/v1/research/stocks/300750.SZ/technicals?lookback_days=3000",
        "domains": ["stock_technical"],
        "required_paths": [
            "data.timeframes.1d", "data.chart.points", "meta.quality.status",
        ],
        "minimum_lengths": {"data.chart.points": 60},
    },
    {
        "id": "bank-fundamentals",
        "subject": "600036.SH 招商银行",
        "path": "/api/v1/research/stocks/600036.SH/fundamentals?periods=12",
        "domains": ["stock_fundamental", "financial_industry"],
        "required_paths": ["data.profile.ts_code", "data.periods", "meta.quality.status"],
        "minimum_lengths": {"data.periods": 4},
    },
    {
        "id": "cyclical-technicals",
        "subject": "601899.SH 紫金矿业",
        "path": "/api/v1/research/stocks/601899.SH/technicals?lookback_days=3000",
        "domains": ["stock_technical", "cyclical_stock"],
        "required_paths": [
            "data.timeframes.1d", "data.chart.points", "meta.quality.status",
        ],
        "minimum_lengths": {"data.chart.points": 60},
    },
    {
        "id": "star50-index-technicals",
        "subject": "000688.SH 科创50",
        "path": "/api/v1/research/instruments/index/000688.SH/technicals?lookback_days=3000",
        "domains": ["cross_asset_technical", "index"],
        "required_paths": [
            "data.timeframes.1d",
            "data.timeframes.1d.chart.points",
            "meta.quality.status",
        ],
        "minimum_lengths": {"data.timeframes.1d.chart.points": 60},
    },
    {
        "id": "semiconductor-etf-technicals",
        "subject": "512480.SH 半导体设备ETF",
        "path": "/api/v1/research/instruments/etf/512480.SH/technicals?lookback_days=3000",
        "domains": ["cross_asset_technical", "etf"],
        "required_paths": [
            "data.timeframes.1d",
            "data.timeframes.1d.chart.points",
            "meta.quality.status",
        ],
        "minimum_lengths": {"data.timeframes.1d.chart.points": 60},
    },
    {
        "id": "gold-spot-technicals",
        "subject": "Au99.99 上金所黄金9999",
        "path": "/api/v1/research/instruments/spot/Au99.99/technicals?lookback_days=3000",
        "domains": ["cross_asset_technical", "precious_metal"],
        "required_paths": [
            "data.timeframes.1d",
            "data.timeframes.1d.chart.points",
            "meta.quality.status",
        ],
        "minimum_lengths": {"data.timeframes.1d.chart.points": 60},
    },
    {
        "id": "macro-regime",
        "subject": "中国宏观环境",
        "path": "/api/v1/research/macro/regime",
        "domains": ["macro_research"],
        "required_paths": ["data.growth", "data.inflation", "data.liquidity", "meta.quality.status"],
    },
    {
        "id": "market-breadth",
        "subject": "A股全市场",
        "path": "/api/v1/research/market/breadth",
        "domains": ["market_research"],
        "required_paths": ["data.trade_date", "data.securities", "meta.methodology"],
    },
    {
        "id": "etf-flows",
        "subject": "ETF份额与轮动",
        "path": "/api/v1/research/etfs/flows?lookback_observations=20&limit=30",
        "domains": ["etf_research"],
        "required_paths": ["data.exposures", "data.funds", "meta.quality.status"],
        "minimum_lengths": {"data.funds": 1},
    },
    {
        "id": "new-energy-industry",
        "subject": "885431.TI A股新能源汽车",
        "path": "/api/v1/research/sectors/ths/885431.TI/fundamentals",
        "domains": ["industry_research"],
        "required_paths": ["data.financials", "data.valuation", "meta.quality.status"],
    },
    {
        "id": "sector-rotation",
        "subject": "同花顺行业与概念板块",
        "path": "/api/v1/research/sectors/ths/rotation?lookback_days=60&limit=20",
        "domains": ["industry_research", "sector_rotation"],
        "required_paths": ["data.leaders", "data.laggards", "meta.quality.status"],
        "minimum_lengths": {"data.leaders": 1},
    },
)


def _lookup(payload: Any, path: str) -> tuple[bool, Any]:
    current = payload
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return False, None
    return True, current


def validate_research_response(
    case: dict[str, Any], status_code: int, payload: Any
) -> list[str]:
    errors: list[str] = []
    if status_code != 200:
        return [f"expected HTTP 200, got {status_code}"]
    for path in case.get("required_paths", []):
        exists, value = _lookup(payload, path)
        if not exists or value is None:
            errors.append(f"required response path is absent: {path}")
    for path, minimum in case.get("minimum_lengths", {}).items():
        exists, value = _lookup(payload, path)
        if not exists or not hasattr(value, "__len__"):
            errors.append(f"length-checked response path is absent: {path}")
        elif len(value) < int(minimum):
            errors.append(
                f"{path} has {len(value)} item(s), expected at least {minimum}"
            )
    return errors


def validation_catalog() -> dict[str, Any]:
    domains = sorted({
        domain
        for case in RESEARCH_VALIDATION_CASES
        for domain in case["domains"]
    })
    return {
        "summary": {
            "cases": len(RESEARCH_VALIDATION_CASES),
            "domains": len(domains),
        },
        "domains": domains,
        "cases": [dict(item) for item in RESEARCH_VALIDATION_CASES],
        "acceptance": (
            "Every case must return HTTP 200 and satisfy its structural and "
            "minimum-history assertions. Readiness is evaluated separately "
            "from endpoint execution."
        ),
    }
