# `dc_index` — 概念板块

- 分类：股票数据/打板专题数据
- 功能：获取每个交易日的概念板块数据，支持按日期查询
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积累6000积分可调取，具体请参阅 积分获取办法
- 官方文档：[doc 362](https://tushare.pro/document/2?doc_id=362)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/board/dc_index.py:DcIndexCollector](../../../collectors/stock/board/dc_index.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 指数代码（支持多个代码同时输入，用逗号分隔） |
| `name` | str | N | 板块名称（例如：人形机器人） |
| `trade_date` | str | N | 交易日期（YYYYMMDD格式，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `idx_type` | str | Y | 板块类型(行业板块、概念板块、地域板块) |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 概念代码 |
| `trade_date` | str | Y | 交易日期 |
| `name` | str | Y | 概念名称 |
| `leading` | str | Y | 领涨股票名称 |
| `leading_code` | str | Y | 领涨股票代码 |
| `pct_change` | float | Y | 涨跌幅 |
| `leading_pct` | float | Y | 领涨股票涨跌幅 |
| `total_mv` | float | Y | 总市值（万元） |
| `turnover_rate` | float | Y | 换手率 |
| `up_num` | int | Y | 上涨家数 |
| `down_num` | int | Y | 下降家数 |
| `idx_type` | str | Y | 板块类型(行业板块、概念板块、地域板块) |
| `level` | str | Y | 行业层级 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "dc_index",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "idx_type": "1"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取2025年1月3日的概念板块列表
df = pro.dc_index(trade_date='20250103', fields='ts_code,name,turnover_rate,up_num,down_num')
```

## 实际返回示例（官方文档）

```text
ts_code   name       turnover_rate  up_num  down_num
0    BK1186.DC   首发经济        8.3700       4        31
1    BK1185.DC   冰雪经济        4.0800       2        32
2    BK1184.DC  人形机器人        4.0800       2        62
3    BK1183.DC   谷子经济        4.6300       2        55
4    BK1182.DC   智谱AI        5.4000       0        33
..         ...    ...           ...     ...       ...
453  BK0498.DC    AB股        1.7300       4        67
454  BK0494.DC   节能环保        2.1600      32       378
455  BK0493.DC    新能源        1.4800      19       184
456  BK0492.DC    煤化工        1.7000      16        56
457  BK0490.DC     军工        2.5200      32       465
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
