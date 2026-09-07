# `dc_concept` — 题材库

- 分类：股票数据/打板专题数据
- 功能：获取概念题材列表，每天盘后更新
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：6000积分可提取数据，具体请参阅 积分获取办法
- 官方文档：[doc 421](https://tushare.pro/document/2?doc_id=421)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/board/dc_concept.py:DcConceptCollector](../../../collectors/stock/board/dc_concept.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期 |
| `theme_code` | str | N | 题材代码(xxxxxx.DC格式) |
| `name` | str | N | 题材名称 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `theme_code` | str | Y | 题材code |
| `trade_date` | str | Y | 交易日期 |
| `name` | str | Y | 名称 |
| `pct_change` | str | Y | 涨跌幅 |
| `hot` | str | Y | 热度 |
| `sort` | str | Y | 排名 |
| `strength` | str | Y | 强度 |
| `z_t_num` | str | Y | 涨停数量 |
| `main_change` | str | Y | 主力净流入（元） |
| `lead_stock` | str | Y | 领涨股票 |
| `lead_stock_code` | str | Y | 领涨股票code |
| `lead_stock_pct_change` | str | Y | 领涨股票涨跌幅 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "dc_concept",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
# 拉取接口dc_concept数据
    df = pro.dc_concept(**{
    "trade_date": "",
    "theme_code": "000053.DC",
    "name": ""
}, fields=[
    "theme_code",
    "trade_date",
    "name",
    "pct_change",
    "hot",
    "sort",
    "strength",
    "z_t_num",
    "main_change",
    "lead_stock",
    "lead_stock_code",
    "lead_stock_pct_change"
])
    print(df)
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
