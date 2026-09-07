# `us_basic` — 美股列表

- 分类：美股数据
- 功能：获取美股列表信息
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：120积分可以试用，5000积分有正式权限
- 官方文档：[doc 252](https://tushare.pro/document/2?doc_id=252)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `classify` | str | N | 股票分类 |
| `list_stauts` | str | N | 上市状态 |
| `offset` | str | N | 开始行数 |
| `limit` | str | N | 每页最大行数 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 美股代码 |
| `name` | str | Y | 中文名称 |
| `enname` | str | N | 英文名称 |
| `classify` | str | Y | 分类:ADR-美国存托凭证；GDR-全球存托凭证；EQ-普通股；PF-优先股 |
| `list_date` | str | Y | 上市日期 |
| `delist_date` | str | Y | 退市日期 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "us_basic",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "AAPL"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

#获取默认美国股票基础信息，单次6000行
df = pro.us_basic()
```

## 实际返回示例（官方文档）

```text
ts_code  name classify list_date delist_date
0       ONCY  None      EQT  20011005        None
1       SCCO  None      EQT  19950124        None
2      KAOCF  None      EQT  19740319        None
3      BOIRF  None      EQT  19880628        None
4      SDXOF  None      EQT  19830304        None
...      ...   ...      ...       ...         ...
5995   ESESQ  None      EQT  20031014        None
5996    TRKX  None      EQT  20000718        None
5997   ELAMF  None      EQT  19960320        None
5998    CZNB  None      EQT  20120724        None
5999   CRRSQ  None      EQT  20010619        None
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_us_basic`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/us_basic.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
