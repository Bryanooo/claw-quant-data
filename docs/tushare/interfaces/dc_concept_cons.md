# `dc_concept_cons` — 题材成分

- 分类：股票数据/打板专题数据
- 功能：获取概念题材的成分股，每天盘后更新
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：6000积分可提取数据，具体请参阅 积分获取办法
- 官方文档：[doc 422](https://tushare.pro/document/2?doc_id=422)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/board/dc_concept_cons.py:DcConceptConsCollector](../../../collectors/stock/board/dc_concept_cons.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `trade_date` | str | N | 交易日期 |
| `theme_code` | str | N | 题材代码 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | str | Y | 交易日期 |
| `name` | str | Y | 名称 |
| `theme_code` | str | Y | 主题code |
| `industry_code` | str | Y | 所属行业code |
| `industry` | str | Y | 所属行业 |
| `reason` | str | Y | 入选原因 |
| `hot_num` | str | Y | 热点排行 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "dc_concept_cons",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
# 拉取接口dc_concept_cons数据
    df = pro.dc_concept_cons(**{
    "ts_code": "000619.SZ",
    "trade_date": "",
    "theme_code": ""
}, fields=[
    "ts_code",
    "trade_date",
    "name",
    "theme_code",
    "industry_code",
    "industry",
    "reason",
    "hot_num"
])
    print(df)
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。
上游文本偶尔包含 PostgreSQL 不接受的 NUL 字符；统一存储边界会保留整行、仅清除
NUL，并在任务 `completion_evidence.sanitization` 中记录数量和受影响字段。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
