"""Investment-calendar queries built from collected, auditable source data."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
import hashlib
from typing import Any, Protocol

from service.clock import business_now
from service.data_service.database import Database


class InvalidInvestmentCalendarRequest(ValueError):
    """Raised when a requested calendar range or filter is invalid."""


class InvestmentCalendarRepositoryProtocol(Protocol):
    def economic_events(self, start_date: date, end_date: date) -> list[dict]: ...

    def index_futures_deliveries(
        self, start_date: date, end_date: date
    ) -> list[dict]: ...

    def source_coverage(self) -> dict[str, dict]: ...


class InvestmentCalendarRepository:
    """Read the latest known revision of each calendar event."""

    def __init__(self, database: Database):
        self.database = database

    def economic_events(self, start_date: date, end_date: date) -> list[dict]:
        return self.database.fetch_all(
            """
            SELECT DISTINCT ON (date, time, currency, country, event)
                   date, time, currency, country, event,
                   value, pre_value, fore_value, _source_collected_at
            FROM tushare_norm_eco_cal
            WHERE date BETWEEN %s AND %s
              AND NULLIF(BTRIM(event), '') IS NOT NULL
            ORDER BY date, time, currency, country, event,
                     _source_collected_at DESC, _last_seen_at DESC,
                     _record_hash DESC
            """,
            (start_date, end_date),
        )

    def index_futures_deliveries(
        self, start_date: date, end_date: date
    ) -> list[dict]:
        return self.database.fetch_all(
            """
            SELECT ts_code, symbol, name, fut_code, d_month, last_ddate,
                   _source_collected_at
            FROM tushare_current_fut_basic
            WHERE exchange = 'CFFEX'
              AND fut_code IN ('IF', 'IH', 'IC', 'IM')
              AND last_ddate ~ '^[0-9]{8}$'
              AND to_date(last_ddate, 'YYYYMMDD') BETWEEN %s AND %s
            ORDER BY last_ddate, fut_code, ts_code
            """,
            (start_date, end_date),
        )

    def source_coverage(self) -> dict[str, dict]:
        economic = self.database.fetch_one(
            """
            SELECT min(date) AS min_date, max(date) AS max_date,
                   max(_source_collected_at) AS last_collected_at,
                   count(*) AS physical_rows
            FROM tushare_norm_eco_cal
            """
        ) or {}
        futures = self.database.fetch_one(
            """
            SELECT min(to_date(last_ddate, 'YYYYMMDD'))
                       FILTER (WHERE last_ddate ~ '^[0-9]{8}$') AS min_date,
                   max(to_date(last_ddate, 'YYYYMMDD'))
                       FILTER (WHERE last_ddate ~ '^[0-9]{8}$') AS max_date,
                   max(_source_collected_at) AS last_collected_at,
                   count(*) FILTER (
                       WHERE exchange = 'CFFEX'
                         AND fut_code IN ('IF', 'IH', 'IC', 'IM')
                   ) AS physical_rows
            FROM tushare_current_fut_basic
            WHERE exchange = 'CFFEX'
              AND fut_code IN ('IF', 'IH', 'IC', 'IM')
            """
        ) or {}
        return {"economic_calendar": economic, "index_futures": futures}


_HIGH_KEYWORDS = (
    "gdp", "国内生产总值", "pmi", "采购经理", "cpi", "消费者物价",
    "消费者价格", "ppi", "生产者物价", "生产者价格", "利率决议",
    "fomc", "非农", "失业率", "m2", "社会融资", "货币供应",
    "工业增加值", "社会消费品零售", "零售销售", "贸易帐", "贸易账",
    "进出口", "央行行长", "美联储主席",
)
_MEDIUM_KEYWORDS = (
    "制造业", "服务业", "工业产出", "工业生产", "就业", "失业金",
    "职位空缺", "平均时薪", "耐用品", "新屋", "成屋", "房价",
    "消费者信心", "经济景气", "商业景气", "通胀", "原油库存",
    "利率", "央行", "美联储", "欧洲央行", "日本央行", "讲话",
)
_MAJOR_ECONOMIES = {
    "中国", "美国", "欧元区", "德国", "法国", "英国", "日本", "加拿大", "澳大利亚",
}
_TYPE_KEYWORDS = (
    ("growth", ("gdp", "国内生产总值", "工业增加值", "工业产出", "工业生产", "零售销售", "社会消费品零售")),
    ("survey", ("pmi", "采购经理", "景气", "消费者信心")),
    ("inflation", ("cpi", "ppi", "物价", "价格指数", "通胀")),
    ("employment", ("非农", "就业", "失业", "职位空缺", "平均时薪")),
    ("central_bank", ("利率决议", "央行", "美联储", "fomc")),
    ("money_credit", ("m2", "社会融资", "货币供应", "新增贷款")),
    ("trade", ("贸易帐", "贸易账", "进出口", "出口", "进口")),
    ("housing", ("新屋", "成屋", "房价", "营建")),
)


def _iso(value: Any) -> Any:
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    return value


def _nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() not in {"", "--", "None"}


def _importance(event: str, country: str | None) -> str:
    normalized = event.casefold()
    if any(keyword in normalized for keyword in _HIGH_KEYWORDS):
        return "high" if country in _MAJOR_ECONOMIES else "medium"
    if any(keyword in normalized for keyword in _MEDIUM_KEYWORDS):
        return "medium"
    return "normal"


def _event_type(event: str) -> str:
    normalized = event.casefold()
    for event_type, keywords in _TYPE_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return event_type
    if "讲话" in normalized:
        return "speech"
    return "other"


def _related_dataset(event: str, country: str | None) -> str | None:
    if country != "中国":
        return None
    normalized = event.casefold()
    if "gdp" in normalized or "国内生产总值" in normalized:
        return "cn_gdp"
    if "pmi" in normalized or "采购经理" in normalized:
        return "cn_pmi"
    return None


def _event_id(*parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


class InvestmentCalendarService:
    MAX_RANGE_DAYS = 63

    def __init__(self, repository: InvestmentCalendarRepositoryProtocol):
        self.repository = repository

    def list_events(
        self,
        *,
        start_date: date,
        end_date: date,
        importance: str = "important",
        country: str | None = None,
        event_type: str | None = None,
    ) -> dict:
        self._validate_range(start_date, end_date)
        if importance not in {"important", "high", "all"}:
            raise InvalidInvestmentCalendarRequest(
                "importance must be one of: important, high, all"
            )

        events = [
            self._economic_event(row)
            for row in self.repository.economic_events(start_date, end_date)
        ]
        events.extend(
            self._delivery_events(
                self.repository.index_futures_deliveries(start_date, end_date)
            )
        )
        events = [
            item for item in events
            if self._matches_filters(item, importance, country, event_type)
        ]
        events.sort(
            key=lambda item: (
                item["event_date"],
                item["event_time"] or "99:99:99",
                {"high": 0, "medium": 1, "normal": 2}[item["importance"]],
                item["title"],
            )
        )

        grouped: dict[str, list[dict]] = defaultdict(list)
        for item in events:
            grouped[item["event_date"]].append(item)
        days = []
        cursor = start_date
        while cursor <= end_date:
            day_events = grouped.get(cursor.isoformat(), [])
            if day_events:
                days.append(
                    {
                        "event_date": cursor.isoformat(),
                        "total_events": len(day_events),
                        "high_events": sum(
                            item["importance"] == "high" for item in day_events
                        ),
                        "macro_events": sum(
                            item["event_type"] != "derivatives"
                            for item in day_events
                        ),
                        "derivative_events": sum(
                            item["event_type"] == "derivatives"
                            for item in day_events
                        ),
                        "scheduled_events": sum(
                            item["status"] == "scheduled" for item in day_events
                        ),
                        "released_events": sum(
                            item["status"] == "released" for item in day_events
                        ),
                        "top_events": [
                            {
                                "event_id": item["event_id"],
                                "title": item["title"],
                                "event_time": item["event_time"],
                                "importance": item["importance"],
                                "event_type": item["event_type"],
                            }
                            for item in day_events[:3]
                        ],
                    }
                )
            cursor += timedelta(days=1)

        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "filters": {
                "importance": importance,
                "country": country,
                "event_type": event_type,
            },
            "summary": {
                "total_events": len(events),
                "days_with_events": len(days),
                "high_events": sum(item["importance"] == "high" for item in events),
                "scheduled_events": sum(item["status"] == "scheduled" for item in events),
                "released_events": sum(item["status"] == "released" for item in events),
            },
            "source_coverage": self._serialize_coverage(
                self.repository.source_coverage()
            ),
            "days": days,
            "events": events,
        }

    def day_events(
        self,
        event_date: date,
        *,
        importance: str = "important",
        country: str | None = None,
        event_type: str | None = None,
    ) -> dict:
        return self.list_events(
            start_date=event_date,
            end_date=event_date,
            importance=importance,
            country=country,
            event_type=event_type,
        )

    def _validate_range(self, start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise InvalidInvestmentCalendarRequest(
                "end_date must not be earlier than start_date"
            )
        if (end_date - start_date).days + 1 > self.MAX_RANGE_DAYS:
            raise InvalidInvestmentCalendarRequest(
                f"calendar range must not exceed {self.MAX_RANGE_DAYS} days"
            )

    @staticmethod
    def _matches_filters(
        event: dict,
        importance: str,
        country: str | None,
        event_type: str | None,
    ) -> bool:
        if importance == "high" and event["importance"] != "high":
            return False
        if importance == "important" and event["importance"] == "normal":
            return False
        if country and event["country"] != country:
            return False
        if event_type and event["event_type"] != event_type:
            return False
        return True

    @staticmethod
    def _economic_event(row: dict) -> dict:
        event_date = row["date"]
        title = str(row.get("event") or "未命名经济事件").strip()
        actual_present = _nonempty(row.get("value"))
        return {
            "event_id": _event_id(
                "eco_cal", event_date, row.get("time"), row.get("currency"),
                row.get("country"), title,
            ),
            "event_date": _iso(event_date),
            "event_time": _iso(row.get("time")),
            "title": title,
            "country": row.get("country") or "未标明",
            "currency": row.get("currency"),
            "event_type": _event_type(title),
            "importance": _importance(title, row.get("country")),
            "status": "released" if actual_present else "scheduled",
            "actual": row.get("value"),
            "forecast": row.get("fore_value"),
            "previous": row.get("pre_value"),
            "source": "eco_cal",
            "source_label": "Tushare 财经日历",
            "source_collected_at": _iso(row.get("_source_collected_at")),
            "related_dataset": _related_dataset(title, row.get("country")),
            "contracts": [],
        }

    @staticmethod
    def _delivery_events(rows: list[dict]) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            raw_date = str(row.get("last_ddate") or "")
            if len(raw_date) == 8 and raw_date.isdigit():
                delivery_date = datetime.strptime(raw_date, "%Y%m%d").date()
                grouped[delivery_date.isoformat()].append(row)

        events = []
        for delivery_date, contracts in grouped.items():
            codes = sorted({str(item.get("fut_code")) for item in contracts})
            months = sorted({str(item.get("d_month")) for item in contracts})
            contract_details = [
                {
                    "ts_code": item.get("ts_code"),
                    "fut_code": item.get("fut_code"),
                    "contract_month": item.get("d_month"),
                    "name": item.get("name"),
                }
                for item in contracts
            ]
            title = f"中金所股指期货 {','.join(months)} 合约交割日"
            events.append(
                {
                    "event_id": _event_id("index_futures", delivery_date, *months),
                    "event_date": delivery_date,
                    "event_time": None,
                    "title": title,
                    "country": "中国",
                    "currency": "CNY",
                    "event_type": "derivatives",
                    "importance": "high",
                    "status": (
                        "completed"
                        if delivery_date < business_now().date().isoformat()
                        else "scheduled"
                    ),
                    "actual": None,
                    "forecast": None,
                    "previous": None,
                    "source": "fut_basic",
                    "source_label": "Tushare 中金所合约基础信息",
                    "source_collected_at": max(
                        (_iso(item.get("_source_collected_at")) or "" for item in contracts),
                        default=None,
                    ),
                    "related_dataset": "fut_basic",
                    "contracts": contract_details,
                    "contract_codes": codes,
                }
            )
        return events

    @staticmethod
    def _serialize_coverage(coverage: dict[str, dict]) -> dict[str, dict]:
        return {
            source: {key: _iso(value) for key, value in facts.items()}
            for source, facts in coverage.items()
        }
