# `tdx_index` — TDX板块信息

- 分类：股票数据/打板专题数据
- 功能：获取板块基础信息，包括概念板块、行业、风格、地域等
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积累6000积分可调取，具体请参阅 积分获取办法
- 官方文档：[doc 376](https://tushare.pro/document/2?doc_id=376)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/board/tdx_index.py:TdxIndexCollector](../../../collectors/stock/board/tdx_index.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 板块代码：xxxxxx.TDX |
| `trade_date` | str | N | 交易日期(格式：YYYYMMDD） |
| `idx_type` | str | N | 板块类型：概念板块、行业板块、风格板块、地区板块 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 板块代码 |
| `trade_date` | str | Y | 交易日期 |
| `name` | str | Y | 板块名称 |
| `idx_type` | str | Y | 板块类型 |
| `idx_count` | int | Y | 成分个数 |
| `total_share` | float | Y | 总股本(亿) |
| `float_share` | float | Y | 流通股(亿) |
| `total_mv` | float | Y | 总市值(亿) |
| `float_mv` | float | Y | 流通市值(亿) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "tdx_index",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取通达信2025年5月13日的概念板块列表
df = pro.tdx_index(trade_date='20250513', fields='ts_code,name,idx_type,idx_count')
```

## 实际返回示例（官方文档）

```text
ts_code           name     idx_type  idx_count
0    880559.TDX   要约收购     风格板块          6
1    880728.TDX   航运概念     概念板块         64
2    880355.TDX   日用化工     行业板块         20
3    880423.TDX   酒店餐饮     行业板块          9
4    880875.TDX   中小银行     风格板块         28
..          ...    ...      ...        ...
477  880528.TDX  军工信息化     概念板块         99
478  880868.TDX   高贝塔值     风格板块        100
479  880430.TDX     航空     行业板块         52
480  880431.TDX     船舶     行业板块         12
481  880914.TDX   军贸概念     概念板块         25
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
