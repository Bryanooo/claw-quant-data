#!/usr/bin/env python3
"""Build a reproducible Tushare documentation/permission/implementation matrix."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from dataclasses import dataclass, field
from datetime import date, timedelta
import html
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_ROOT_URL = "http://tushare.pro/document/2?doc_id=14"
DOC_FETCH_URL = "http://tushare.pro/document/2?doc_id={doc_id}"
DOC_URL = "https://tushare.pro/document/2?doc_id={doc_id}"
API_URL = "http://api.tushare.pro"
USER_AGENT = "claw-quant-data-interface-audit/1.0"

EQUIVALENT_IMPLEMENTATIONS = {
    "income": "income_vip",
    "balancesheet": "balancesheet_vip",
    "cashflow": "cashflow_vip",
    "forecast": "forecast_vip",
    "express": "express_vip",
    "fina_indicator": "fina_indicator_vip",
    "fina_mainbz": "fina_mainbz_vip",
}


@dataclass
class DocumentEntry:
    doc_id: int
    path: tuple[str, ...]
    title: str = ""
    description: str = ""
    permission_text: str = ""
    api_names: tuple[str, ...] = ()
    input_parameters: list[dict[str, str]] = field(default_factory=list)
    output_parameters: list[dict[str, str]] = field(default_factory=list)
    code_examples: list[str] = field(default_factory=list)
    response_examples: list[str] = field(default_factory=list)
    first_output_field: str = ""
    fetch_error: str = ""


def load_env_token() -> str:
    token = os.getenv("TUSHARE_TOKEN", "")
    if token:
        return token
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            if raw_line.startswith("TUSHARE_TOKEN="):
                return raw_line.split("=", 1)[1].strip()
    raise RuntimeError("TUSHARE_TOKEN is not configured")


def fetch_url(url: str, *, attempts: int = 8) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=15) as response:
                return response.read()
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(min(attempt * 0.5, 3))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def _direct_anchor_text(list_item) -> str:
    anchor = list_item.find("a", recursive=False)
    return anchor.get_text(" ", strip=True) if anchor else ""


def discover_document_leaves(root_html: bytes) -> list[DocumentEntry]:
    soup = BeautifulSoup(root_html, "html.parser")
    tree = soup.select_one("#jstree")
    if tree is None:
        raise RuntimeError("Tushare documentation tree was not found")

    entries: dict[int, DocumentEntry] = {}
    for anchor in tree.select('a[href*="doc_id="]'):
        list_item = anchor.find_parent("li")
        if list_item is None or list_item.find("ul", recursive=False) is not None:
            continue
        match = re.search(r"doc_id=(\d+)", anchor.get("href", ""))
        if not match:
            continue
        path = tuple(
            text
            for text in (
                _direct_anchor_text(parent)
                for parent in reversed(anchor.find_parents("li"))
            )
            if text
        )
        doc_id = int(match.group(1))
        entries[doc_id] = DocumentEntry(doc_id=doc_id, path=path)
    return sorted(entries.values(), key=lambda item: (item.path, item.doc_id))


def _normalized_text(element) -> str:
    return " ".join(element.get_text(" ", strip=True).split())


def _extract_line(text: str, labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:^|\s)(?:{label_pattern})\s*[：:]\s*(.+?)"
        rf"(?=\s(?:接口(?:名称)?|描述|限量|权限(?:要求)?|积分(?:要求)?|注意|说明)\s*[：:]"
        rf"|\s(?:输入参数|输出参数|输出指标|接口示例|接口用例|接口用法|数据样例|使用文档)(?:\s|$)|$)",
        text,
    )
    return match.group(1).strip() if match else ""


def _extract_parameters(
    content,
) -> tuple[list[dict[str, str]], list[dict[str, str]], str]:
    tables = content.select("table")
    input_parameters: list[dict[str, str]] = []
    output_parameters: list[dict[str, str]] = []
    first_output_field = ""
    for table in tables:
        rows = []
        for row in table.select("tr"):
            values = [_normalized_text(cell) for cell in row.select("th,td")]
            if values:
                rows.append(values)
        if not rows:
            continue
        header = rows[0]
        if header[:3] == ["名称", "类型", "必选"] and not input_parameters:
            for values in rows[1:]:
                padded = values + [""] * (4 - len(values))
                input_parameters.append(
                    {
                        "name": padded[0],
                        "type": padded[1],
                        "required": padded[2],
                        "description": padded[3],
                    }
                )
        elif header and header[0] == "名称" and "描述" in header and not output_parameters:
            for values in rows[1:]:
                padded = values + [""] * (4 - len(values))
                output_parameters.append(
                    {
                        "name": padded[0],
                        "type": padded[1],
                        "default": padded[2],
                        "description": padded[3],
                    }
                )
            if output_parameters:
                first_output_field = output_parameters[0]["name"]
    return input_parameters, output_parameters, first_output_field


def _extract_examples(content, api_names: tuple[str, ...]) -> tuple[list[str], list[str]]:
    code_examples: list[str] = []
    response_examples: list[str] = []
    for block in content.select("pre"):
        value = block.get_text().strip()
        if not value:
            continue
        compact = value[:4000]
        looks_like_code = any(
            marker in value
            for marker in ("pro_api", "ts.pro_bar", "pro.query", "requests.post")
        ) or any(f"pro.{api_name}" in value for api_name in api_names)
        target = code_examples if looks_like_code else response_examples
        if compact not in target and len(target) < 3:
            target.append(compact)
    return code_examples, response_examples


def parse_document(entry: DocumentEntry, raw_html: bytes) -> None:
    soup = BeautifulSoup(raw_html, "html.parser")
    content = soup.select_one("div.content")
    if content is None:
        entry.fetch_error = "document content not found"
        return

    heading = content.find(["h1", "h2", "h3"])
    entry.title = _normalized_text(heading) if heading else entry.path[-1]
    text = _normalized_text(content)
    entry.description = _extract_line(text, ("描述",))
    entry.permission_text = _extract_line(
        text,
        ("权限", "权限要求", "积分", "积分要求"),
    )

    api_names: list[str] = []
    for pattern in (
        r"接口\s*(?:名称|名)?\s*[：:]\s*([A-Za-z][A-Za-z0-9_]*)",
        r"api_name[：:]\s*([A-Za-z][A-Za-z0-9_]*)",
    ):
        api_names.extend(re.findall(pattern, text))
    if not api_names:
        code_text = "\n".join(block.get_text(" ") for block in content.select("pre,code"))
        for pattern in (
            r"\.query\(\s*['\"]([A-Za-z][A-Za-z0-9_]*)['\"]",
            r"\bpro\.([A-Za-z][A-Za-z0-9_]*)\s*\(",
        ):
            api_names.extend(re.findall(pattern, code_text))
            if api_names:
                break
    ignored = {"query", "pro_api", "set_token", "DataFrame"}
    entry.api_names = tuple(dict.fromkeys(name for name in api_names if name not in ignored))
    (
        entry.input_parameters,
        entry.output_parameters,
        entry.first_output_field,
    ) = _extract_parameters(content)
    entry.code_examples, entry.response_examples = _extract_examples(
        content, entry.api_names
    )


def scan_implementation() -> dict[str, set[str]]:
    implemented: dict[str, set[str]] = {}
    roots = [PROJECT_ROOT / "collectors", PROJECT_ROOT / "service"]
    for root in roots:
        for path in root.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            relative = str(path.relative_to(PROJECT_ROOT))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name.endswith("Collector"):
                    for statement in node.body:
                        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
                            continue
                        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                        value = statement.value
                        for target in targets:
                            if (
                                isinstance(target, ast.Name)
                                and target.id in {"API_NAME", "INTERFACE_NAME"}
                                and isinstance(value, ast.Constant)
                                and isinstance(value.value, str)
                                and value.value
                            ):
                                implemented.setdefault(value.value, set()).add(
                                    f"{relative}:{node.name}"
                                )
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                    if name not in {
                        "query", "pro_api", "set_token", "get", "post", "execute",
                        "cursor", "commit", "rollback", "close", "fetch", "store",
                    }:
                        receiver = node.func.value
                        is_pro_receiver = (
                            isinstance(receiver, ast.Name) and receiver.id == "pro"
                        ) or (
                            isinstance(receiver, ast.Attribute) and receiver.attr == "pro"
                        ) or (
                            isinstance(receiver, ast.Call)
                            and isinstance(receiver.func, ast.Name)
                            and receiver.func.id == "get_pro"
                        )
                        if is_pro_receiver:
                            implemented.setdefault(name, set()).add(relative)
    return implemented


def _category_text(entry: DocumentEntry) -> str:
    return "/".join(entry.path[:-1])


def sample_value(name: str, entry: DocumentEntry, description: str) -> Any:
    category = _category_text(entry)
    lowered = f"{name} {description} {category}".lower()
    today = date.today()
    recent = today.strftime("%Y%m%d")
    start = (today - timedelta(days=30)).strftime("%Y%m%d")
    values: dict[str, Any] = {
        "trade_date": recent,
        "date": recent,
        "cal_date": recent,
        "start_date": start,
        "end_date": recent,
        "ann_date": recent,
        "period": f"{today.year - 1}1231",
        "report_date": f"{today.year - 1}1231",
        "month": today.strftime("%Y%m"),
        "start_month": (today.replace(day=1) - timedelta(days=90)).strftime("%Y%m"),
        "end_month": today.strftime("%Y%m"),
        "year": str(today.year - 1),
        "quarter": "4",
        "limit": 1,
        "offset": 0,
        "freq": "D",
        "asset": "E",
        "adj": "qfq",
        "adjfactor": "qfq",
        "is_open": "1",
        "is_hs": "N",
        "list_status": "L",
        "curr_type": "USD",
        "currency": "USD",
        "country": "美国",
        "lang": "cn",
        "source": "sina",
        "src": "sina",
        "report_type": "Q4",
    }
    if name in values:
        return values[name]
    if name in {"ts_code", "code", "symbol"}:
        if "港股" in category:
            return "00001.HK"
        if "美股" in category:
            return "AAPL"
        if "期货" in category:
            return "CU.SHF"
        if "期权" in category:
            return "10000001.SH"
        if "可转债" in category or "债券" in category:
            return "110000.SH"
        if "基金" in category or "ETF" in category:
            return "510300.SH"
        if "指数" in category:
            return "000001.SH"
        if "现货" in category:
            return "Au99.99.SGE"
        if "外汇" in category:
            return "EURUSD.FXCM"
        return "000001.SZ"
    if name in {"index_code", "index", "idx_code"}:
        return "000001.SH"
    if name in {"fund_code"}:
        return "510300.SH"
    if name in {"exchange", "market"}:
        if "期货" in category:
            return "SHFE"
        if "港股" in category:
            return "HKEX"
        if "美股" in category:
            return "NASDAQ"
        if "外汇" in category:
            return "FXCM"
        return "SSE"
    if name in {"type", "data_type", "classify"}:
        if "外汇" in category:
            return "FX"
        return "1"
    if "代码" in description:
        return "000001.SZ"
    if "日期" in description or "时间" in description:
        return recent
    if "类型" in description:
        return "1"
    if "名称" in description:
        return "测试"
    if any(token in lowered for token in ("int", "数量", "页码")):
        return 1
    return "1"


def build_probe_params(entry: DocumentEntry, *, mutation_safe: bool) -> dict[str, Any]:
    if mutation_safe:
        return {}
    parameters = entry.input_parameters
    result: dict[str, Any] = {}
    for parameter in parameters:
        if parameter["required"].upper() == "Y":
            result[parameter["name"]] = sample_value(
                parameter["name"], entry, parameter["description"]
            )
    if result:
        return result
    by_name = {item["name"]: item for item in parameters}
    for candidates in (
        ("trade_date",),
        ("ts_code",),
        ("period",),
        ("month",),
        ("start_date", "end_date"),
        ("date",),
    ):
        if all(candidate in by_name for candidate in candidates):
            return {
                candidate: sample_value(
                    candidate, entry, by_name[candidate]["description"]
                )
                for candidate in candidates
            }
    return result


def call_api(token: str, api_name: str, params: dict[str, Any], fields: str) -> dict:
    payload = json.dumps(
        {"api_name": api_name, "token": token, "params": params, "fields": fields}
    ).encode("utf-8")
    request = Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            with urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(attempt)
    return {"code": "transport_error", "msg": str(last_error), "data": None}


def classify_permission(code: Any, message: str) -> tuple[str, str]:
    if code == 0:
        return "有权限", "接口返回成功"
    if "频率超限" in message or "访问频率" in message:
        return "有权限（当前限频）", "Tushare 明确返回该接口的频率上限"
    if code == 40203 and ("没有接口" in message or "访问权限" in message):
        return "无权限", "Tushare 明确返回无访问权限"
    if code == 50101 or "参数校验失败" in message:
        return "有权限", "权限层已通过，接口进入参数校验"
    if code == 40101 or "正确的接口名" in message:
        return "接口无效/已下线", "Tushare 不再识别该 api_name"
    if code == "transport_error":
        return "未确认", "网络请求失败"
    return "未确认", f"未识别返回码 {code}"


def is_mutating(entry: DocumentEntry) -> bool:
    text = f"{entry.title} {' '.join(entry.api_names)}"
    return any(word in text for word in ("保存", "删除", "创建", "修改"))


def generate_rows(entries: list[DocumentEntry], token: str) -> list[dict[str, Any]]:
    implementations = scan_implementation()
    rows: list[dict[str, Any]] = []
    total_apis = sum(max(1, len(entry.api_names)) for entry in entries)
    current = 0
    for entry in entries:
        api_names = entry.api_names or ("",)
        for api_name in api_names:
            current += 1
            if not api_name:
                response = {"code": "not_documented", "msg": "未提取到 api_name"}
                permission_status, permission_basis = "非API数据服务", "文档未声明 api_name"
            elif api_name == "pro_bar":
                response = {
                    "code": "sdk_only",
                    "msg": "SDK 组合接口，不支持 HTTP；权限取决于底层行情接口",
                }
                permission_status = "依底层接口权限"
                permission_basis = "官方文档明确说明 pro_bar 不支持 HTTP 调用"
            else:
                params = build_probe_params(entry, mutation_safe=is_mutating(entry))
                response = call_api(token, api_name, params, entry.first_output_field)
                permission_status, permission_basis = classify_permission(
                    response.get("code"), str(response.get("msg", ""))
                )
            exact_refs = implementations.get(api_name, set()) if api_name else set()
            equivalent_name = EQUIVALENT_IMPLEMENTATIONS.get(api_name, "")
            equivalent_refs = implementations.get(equivalent_name, set()) if equivalent_name else set()
            implementation_refs = sorted(exact_refs | equivalent_refs)
            if exact_refs:
                implementation_status = "已实现"
            elif equivalent_refs:
                implementation_status = f"已实现（{equivalent_name}）"
            elif permission_status.startswith("有权限") and is_mutating(entry):
                implementation_status = "已封装（写接口，不进入采集调度）"
                implementation_refs = ["service/tushare_catalog.py:TushareInterfaceCatalog"]
            elif permission_status.startswith("有权限"):
                implementation_status = "已实现（契约通用采集器：原始层+强类型标准表）"
                implementation_refs = ["collectors/tushare_raw.py:CatalogRawCollector"]
            else:
                implementation_status = "未实现"
            data = response.get("data") or {}
            rows.append(
                {
                    "来源": "Tushare官方目录",
                    "一级分类": entry.path[0] if entry.path else "",
                    "分类路径": "/".join(entry.path[:-1]),
                    "文档标题": entry.title or (entry.path[-1] if entry.path else ""),
                    "api_name": api_name,
                    "doc_id": entry.doc_id,
                    "官方文档": DOC_URL.format(doc_id=entry.doc_id),
                    "官方权限说明": entry.permission_text,
                    "官方描述": entry.description,
                    "必填参数": ",".join(
                        item["name"]
                        for item in entry.input_parameters
                        if item["required"].upper() == "Y"
                    ),
                    "Token权限": permission_status,
                    "权限判定依据": permission_basis,
                    "探测返回码": response.get("code", ""),
                    "探测消息": str(response.get("msg", ""))[:500],
                    "探测返回行数": len(data.get("items") or []),
                    "claw_quant实现": implementation_status,
                    "实现位置": "; ".join(implementation_refs),
                }
            )
            if current % 20 == 0 or current == total_apis:
                print(f"permission probes: {current}/{total_apis}", flush=True)
            time.sleep(0.08)

    official_names = {row["api_name"] for row in rows if row["api_name"]}
    for api_name in sorted(set(implementations) - official_names):
        response = call_api(token, api_name, {}, "")
        permission_status, permission_basis = classify_permission(
            response.get("code"), str(response.get("msg", ""))
        )
        data = response.get("data") or {}
        rows.append(
            {
                "来源": "claw-quant扩展/历史接口",
                "一级分类": "项目扩展接口",
                "分类路径": "项目扩展接口",
                "文档标题": "当前官方目录未列出",
                "api_name": api_name,
                "doc_id": "",
                "官方文档": "",
                "官方权限说明": "当前官方目录未列出",
                "官方描述": "claw-quant 代码中存在直接实现",
                "必填参数": "",
                "Token权限": permission_status,
                "权限判定依据": permission_basis,
                "探测返回码": response.get("code", ""),
                "探测消息": str(response.get("msg", ""))[:500],
                "探测返回行数": len(data.get("items") or []),
                "claw_quant实现": "已实现",
                "实现位置": "; ".join(sorted(implementations[api_name])),
            }
        )
        time.sleep(0.08)
    return rows


def write_reports(rows: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "tushare_interface_matrix.csv"
    md_path = output_dir / "tushare_interface_matrix.md"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    official_rows = [row for row in rows if row["来源"] == "Tushare官方目录"]
    interface_rows = [row for row in official_rows if row["api_name"]]
    unique_interfaces = {row["api_name"]: row for row in interface_rows}
    permission_counts: dict[str, int] = {}
    implementation_counts: dict[str, int] = {}
    for row in unique_interfaces.values():
        permission_counts[row["Token权限"]] = permission_counts.get(row["Token权限"], 0) + 1
        implementation_counts[row["claw_quant实现"]] = implementation_counts.get(row["claw_quant实现"], 0) + 1

    lines = [
        "# Tushare 接口、Token 权限与 claw-quant 实现矩阵",
        "",
        f"生成日期：{date.today().isoformat()}",
        "",
        f"- 官方叶子文档：{len({row['doc_id'] for row in official_rows})}",
        f"- 官方接口记录：{len(interface_rows)}",
        f"- 唯一 api_name：{len(unique_interfaces)}",
        f"- claw-quant 扩展/历史接口：{sum(row['来源'] != 'Tushare官方目录' for row in rows)}",
        f"- Token 权限：{json.dumps(permission_counts, ensure_ascii=False, sort_keys=True)}",
        f"- claw-quant 实现：{json.dumps(implementation_counts, ensure_ascii=False, sort_keys=True)}",
        "",
        "判定规则：返回码 0 为有权限；40203 结合消息区分无权限与当前限频；",
        "50101 表示权限层已通过、请求进入参数校验，因此判为有权限；40101 表示接口名已无效或接口已下线。",
        "保存/删除类接口只发送空参数请求，避免产生账户写入。",
        "",
        "## 分类汇总（按唯一 api_name）",
        "",
        "| 一级分类 | 接口数 | Token可访问 | 无权限 | 条件/失效 | claw-quant已实现 | 未实现 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for category in sorted({row["一级分类"] for row in unique_interfaces.values()}):
        category_rows = [
            row for row in unique_interfaces.values() if row["一级分类"] == category
        ]
        accessible = sum(row["Token权限"].startswith("有权限") for row in category_rows)
        denied = sum(row["Token权限"] == "无权限" for row in category_rows)
        conditional = len(category_rows) - accessible - denied
        implemented = sum(row["claw_quant实现"] != "未实现" for row in category_rows)
        lines.append(
            f"| {category} | {len(category_rows)} | {accessible} | {denied} | "
            f"{conditional} | {implemented} | {len(category_rows) - implemented} |"
        )
    lines.extend(
        [
        "",
        "## 完整矩阵",
        "",
        "| 来源 | 分类 | 文档 | api_name | Token权限 | claw-quant | 返回码 | 官方链接 |",
        "|---|---|---|---|---|---|---:|---|",
        ]
    )
    for row in rows:
        title = str(row["文档标题"]).replace("|", "\\|")
        doc_link = (
            f"[doc {row['doc_id']}]({row['官方文档']})"
            if row["官方文档"]
            else ""
        )
        lines.append(
            f"| {row['来源']} | {row['分类路径']} | {title} | `{row['api_name']}` | "
            f"{row['Token权限']} | {row['claw_quant实现']} | {row['探测返回码']} | "
            f"{doc_link} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, md_path


def _markdown_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def _code_link(reference: str, *, from_interface: bool) -> str:
    path, _, symbol = reference.partition(":")
    prefix = "../../../" if from_interface else "../../"
    label = f"{path}:{symbol}" if symbol else path
    return f"[{label}]({prefix}{path})"


def _implementation_mode(status: str) -> str:
    if "契约通用采集器" in status or "通用原始数据采集器" in status:
        return "generic_raw"
    if "写接口" in status:
        return "safe_write_wrapper"
    if "（" in status and status.startswith("已实现"):
        return "equivalent_specialized"
    if status == "已实现":
        return "specialized"
    return "unavailable"


def _write_contract_markdown(contract: dict[str, Any], target: Path) -> None:
    http = contract["http"]
    implementation = contract["implementation"]
    permission = contract["permission"]
    official_links = "、".join(
        f"[doc {doc_id}]({url})"
        for doc_id, url in zip(contract["doc_ids"], contract["official_urls"])
    ) or "当前官方目录未提供"
    code_links = "、".join(
        _code_link(reference, from_interface=True)
        for reference in implementation["references"]
    ) or "无"
    http_label = (
        "不支持（SDK 组合接口）"
        if not http["supported"]
        else f"`{http['method']} {http['url']}`"
    )
    lines = [
        f"# `{contract['api_name']}` — {contract['title']}",
        "",
        f"- 分类：{contract['category_path'] or '项目扩展接口'}",
        f"- 功能：{contract['description'] or contract['title']}",
        f"- Token 权限：**{permission['status']}**（{permission['basis']}）",
        f"- 官方权限要求：{permission['official_text'] or '官方页面未单独声明'}",
        f"- 官方文档：{official_links}",
        f"- HTTP：{http_label}",
        f"- claw-quant：{implementation['status']}；代码：{code_links}",
        "",
        "## 输入契约",
        "",
    ]
    inputs = contract["input_parameters"]
    if inputs:
        lines.extend(
            [
                "| 参数 | 类型 | 必选 | 说明 |",
                "|---|---|:---:|---|",
                *[
                    f"| `{_markdown_cell(item['name'])}` | {_markdown_cell(item['type'])} | "
                    f"{_markdown_cell(item['required'])} | {_markdown_cell(item['description'])} |"
                    for item in inputs
                ],
            ]
        )
    else:
        lines.append("当前官方目录没有可提取的输入参数表；调用时仍由 Tushare 服务端完成最终校验。")
    lines.extend(["", "## 输出契约", ""])
    outputs = contract["output_parameters"]
    if outputs:
        lines.extend(
            [
                "| 字段 | 类型 | 默认显示 | 说明 |",
                "|---|---|:---:|---|",
                *[
                    f"| `{_markdown_cell(item['name'])}` | {_markdown_cell(item['type'])} | "
                    f"{_markdown_cell(item['default'])} | {_markdown_cell(item['description'])} |"
                    for item in outputs
                ],
            ]
        )
    else:
        lines.append("当前官方目录没有可提取的输出字段表。")

    if http["supported"]:
        request_example = json.dumps(
            {
                "api_name": contract["api_name"],
                "token": "${TUSHARE_TOKEN}",
                "params": contract["example_parameters"],
                "fields": "",
            },
            ensure_ascii=False,
            indent=2,
        )
        lines.extend(
            [
                "",
                "## HTTP 请求示例",
                "",
                "```bash",
                f"curl -X POST '{http['url']}' \\",
                "  -H 'Content-Type: application/json' \\",
                "  -d '" + request_example.replace("'", "'\\''") + "'",
                "```",
            ]
        )
    if contract["code_examples"]:
        lines.extend(["", "## 官方 SDK 示例", "", "```python"])
        lines.append(contract["code_examples"][0])
        lines.append("```")
    if contract["response_examples"]:
        lines.extend(["", "## 实际返回示例（官方文档）", "", "```text"])
        lines.append(contract["response_examples"][0])
        lines.append("```")
    lines.extend(
        [
            "",
            "## claw-quant 存储契约",
            "",
            (
                "该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。"
                if implementation["mode"] in {"specialized", "equivalent_specialized"}
                else "该只读接口由契约通用采集器先写入 `tushare_raw_record`，再转换到接口专属强类型标准表。请求参数和每行原始 JSON 均保留；"
                "`(api_name, request_hash, record_hash)` 保证重复采集幂等。"
                if implementation["mode"] == "generic_raw"
                else "这是账户写接口，只提供显式调用契约，不进入采集任务和定时调度。"
                if implementation["mode"] == "safe_write_wrapper"
                else "当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。"
            ),
            "",
            "> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。",
            "",
        ]
    )
    target.write_text("\n".join(lines), encoding="utf-8")


def write_contract_docs(
    entries: list[DocumentEntry], rows: list[dict[str, Any]], docs_dir: Path
) -> tuple[Path, Path]:
    """Write the human and machine-readable interface contract catalog."""
    docs_dir.mkdir(parents=True, exist_ok=True)
    interfaces_dir = docs_dir / "interfaces"
    interfaces_dir.mkdir(parents=True, exist_ok=True)

    entries_by_doc = {entry.doc_id: entry for entry in entries}
    rows_by_api: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["api_name"]:
            rows_by_api.setdefault(row["api_name"], []).append(row)

    contracts: list[dict[str, Any]] = []
    for api_name, api_rows in sorted(rows_by_api.items()):
        primary = api_rows[0]
        document_entries = [
            entries_by_doc[int(row["doc_id"])]
            for row in api_rows
            if str(row["doc_id"]).isdigit() and int(row["doc_id"]) in entries_by_doc
        ]
        entry = document_entries[0] if document_entries else None
        mutating = any(is_mutating(item) for item in document_entries)
        permission_status = primary["Token权限"]
        collectable = permission_status.startswith("有权限") and not mutating
        refs = [
            reference.strip()
            for reference in str(primary["实现位置"]).split(";")
            if reference.strip()
        ]
        example_parameters = (
            build_probe_params(entry, mutation_safe=mutating) if entry else {}
        )
        contract = {
            "api_name": api_name,
            "title": primary["文档标题"],
            "category": primary["一级分类"],
            "category_path": primary["分类路径"],
            "description": primary["官方描述"],
            "doc_ids": [int(row["doc_id"]) for row in api_rows if str(row["doc_id"]).isdigit()],
            "official_urls": [row["官方文档"] for row in api_rows if row["官方文档"]],
            "http": {
                "supported": api_name != "pro_bar",
                "method": "POST",
                "url": API_URL,
            },
            "read_only": not mutating,
            "collectable": collectable,
            "input_parameters": entry.input_parameters if entry else [],
            "output_parameters": entry.output_parameters if entry else [],
            "example_parameters": example_parameters,
            "code_examples": entry.code_examples if entry else [],
            "response_examples": entry.response_examples if entry else [],
            "permission": {
                "status": permission_status,
                "basis": primary["权限判定依据"],
                "official_text": primary["官方权限说明"],
                "probed_code": primary["探测返回码"],
                "probed_message": primary["探测消息"],
            },
            "implementation": {
                "status": primary["claw_quant实现"],
                "mode": _implementation_mode(primary["claw_quant实现"]),
                "references": refs,
            },
        }
        contracts.append(contract)
        _write_contract_markdown(contract, interfaces_dir / f"{api_name}.md")

    contracts_path = docs_dir / "contracts.json"
    contracts_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_date": date.today().isoformat(),
                "http_protocol_document": "https://tushare.pro/document/1?doc_id=40",
                "permission_document": "https://tushare.pro/document/1?doc_id=108",
                "interfaces": contracts,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    accessible = sum(item["collectable"] for item in contracts)
    implemented = sum(item["implementation"]["mode"] != "unavailable" for item in contracts)
    official_count = sum(bool(item["doc_ids"]) for item in contracts)
    extension_count = len(contracts) - official_count
    official_permissions = Counter(
        item["permission"]["status"] for item in contracts if item["doc_ids"]
    )
    lines = [
        "# Tushare 全接口目录与 claw-quant 实现索引",
        "",
        f"生成日期：{date.today().isoformat()}。共收录 **{len(contracts)}** 个唯一 `api_name`；"
        f"当前 Token 可执行只读采集 **{accessible}** 个；已实现或安全封装 **{implemented}** 个。",
        "",
        f"- 当前官方目录接口：{official_count} 个；claw-quant 有效历史/扩展接口：{extension_count} 个",
        "- 官方接口权限："
        + "、".join(
            f"{status} {count} 个"
            for status, count in sorted(official_permissions.items())
        ),
        "- HTTP 协议：[官方调用说明](https://tushare.pro/document/1?doc_id=40)",
        "- 权限规则：[官方权限说明](https://tushare.pro/document/1?doc_id=108)",
        "- 机器可读契约：[contracts.json](contracts.json)",
        "- 原始审计证据：[CSV](../../reports/tushare_interface_matrix.csv) / [Markdown](../../reports/tushare_interface_matrix.md)",
        "",
        "权限来自真实 Token 的安全探测。保存、删除类接口只探测空参数，不会更改用户数据；"
        "它们仅做安全封装，不进入采集调度。`pro_bar` 是 SDK 组合接口，不支持 HTTP。",
        "",
        "## 完整接口列表",
        "",
        "| HTTP | 接口名 | 功能 | Token权限 | claw-quant实现 | 官方详情 | 契约 | 实现代码 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for contract in contracts:
        official = "、".join(
            f"[doc {doc_id}]({url})"
            for doc_id, url in zip(contract["doc_ids"], contract["official_urls"])
        ) or "—"
        code = "、".join(
            _code_link(reference, from_interface=False)
            for reference in contract["implementation"]["references"]
        ) or "—"
        http_label = (
            f"{contract['http']['method']} {contract['http']['url']}"
            if contract["http"]["supported"]
            else "SDK only"
        )
        lines.append(
            f"| {_markdown_cell(http_label)} | [`{contract['api_name']}`](interfaces/{contract['api_name']}.md) | "
            f"{_markdown_cell(contract['description'] or contract['title'])} | "
            f"{_markdown_cell(contract['permission']['status'])} | "
            f"{_markdown_cell(contract['implementation']['status'])} | {official} | "
            f"[输入/输出/示例](interfaces/{contract['api_name']}.md) | {code} |"
        )
    index_path = docs_dir / "README.md"
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index_path, contracts_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "reports",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("/tmp/claw-quant-tushare-docs"),
    )
    parser.add_argument("--refresh-docs", action="store_true")
    args = parser.parse_args()

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    root_cache = args.cache_dir / "14.html"
    if args.refresh_docs or not root_cache.exists():
        root_cache.write_bytes(fetch_url(DOC_ROOT_URL))
    entries = discover_document_leaves(root_cache.read_bytes())
    print(f"official leaf documents: {len(entries)}", flush=True)

    def download(entry: DocumentEntry) -> tuple[int, bytes]:
        return entry.doc_id, fetch_url(DOC_FETCH_URL.format(doc_id=entry.doc_id))

    pending = [
        entry
        for entry in entries
        if args.refresh_docs or not (args.cache_dir / f"{entry.doc_id}.html").exists()
    ]
    if pending:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(download, entry): entry for entry in pending}
            completed = 0
            for future in as_completed(futures):
                entry = futures[future]
                try:
                    doc_id, body = future.result()
                    (args.cache_dir / f"{doc_id}.html").write_bytes(body)
                except Exception as exc:
                    entry.fetch_error = f"{type(exc).__name__}: {exc}"
                completed += 1
                if completed % 25 == 0 or completed == len(pending):
                    print(f"documents downloaded: {completed}/{len(pending)}", flush=True)

    for index, entry in enumerate(entries, start=1):
        cache_path = args.cache_dir / f"{entry.doc_id}.html"
        try:
            if not cache_path.exists():
                if not entry.fetch_error:
                    entry.fetch_error = "document was not downloaded"
            else:
                parse_document(entry, cache_path.read_bytes())
        except Exception as exc:
            entry.fetch_error = f"{type(exc).__name__}: {exc}"
        if index % 50 == 0 or index == len(entries):
            print(f"documents parsed: {index}/{len(entries)}", flush=True)

    failed_documents = [entry for entry in entries if entry.fetch_error]
    if failed_documents:
        failed = ", ".join(str(entry.doc_id) for entry in failed_documents)
        raise RuntimeError(f"document fetch/parse incomplete: {failed}")

    rows = generate_rows(entries, load_env_token())
    csv_path, md_path = write_reports(rows, args.output_dir)
    index_path, contracts_path = write_contract_docs(
        entries, rows, PROJECT_ROOT / "docs" / "tushare"
    )
    print(f"CSV: {csv_path}")
    print(f"Markdown: {md_path}")
    print(f"Contract index: {index_path}")
    print(f"Machine contracts: {contracts_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
