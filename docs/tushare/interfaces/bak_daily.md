# `bak_daily` — 备用行情

- 分类：股票数据/行情数据
- 功能：获取备用行情，包括特定的行情指标(数据从2017年中左右开始，早期有几天数据缺失，近期正常)
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 255](https://tushare.pro/document/2?doc_id=255)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `trade_date` | str | N | 交易日期 |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `offset` | str | N | 开始行数 |
| `limit` | str | N | 最大行数 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | str | Y | 交易日期 |
| `name` | str | Y | 股票名称 |
| `pct_change` | float | Y | 涨跌幅 |
| `close` | float | Y | 收盘价 |
| `change` | float | Y | 涨跌额 |
| `open` | float | Y | 开盘价 |
| `high` | float | Y | 最高价 |
| `low` | float | Y | 最低价 |
| `pre_close` | float | Y | 昨收价 |
| `vol_ratio` | float | Y | 量比 |
| `turn_over` | float | Y | 换手率 |
| `swing` | float | Y | 振幅 |
| `vol` | float | Y | 成交量 |
| `amount` | float | Y | 成交额 |
| `selling` | float | Y | 内盘（主动卖，手） |
| `buying` | float | Y | 外盘（主动买， 手） |
| `total_share` | float | Y | 总股本(亿) |
| `float_share` | float | Y | 流通股本(亿) |
| `pe` | float | Y | 市盈(动) |
| `industry` | str | Y | 所属行业 |
| `area` | str | Y | 所属地域 |
| `float_mv` | float | Y | 流通市值 |
| `total_mv` | float | Y | 总市值 |
| `avg_price` | float | Y | 平均价 |
| `strength` | float | Y | 强弱度(%) |
| `activity` | float | Y | 活跃度(%) |
| `avg_turnover` | float | Y | 笔换手 |
| `attack` | float | Y | 攻击波(%) |
| `interval_3` | float | Y | 近3月涨幅 |
| `interval_6` | float | Y | 近6月涨幅 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "bak_daily",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.bak_daily(trade_date='20211012', fields='trade_date,ts_code,name,close,open')
```

## 实际返回示例（官方文档）

```text
ts_code     trade_date      name  close   open
0     300605.SZ   20211012  恒锋信息  14.86  12.65
1     301017.SZ   20211012  漱玉平民  25.21  20.82
2     300755.SZ   20211012  华致酒行  40.45  37.01
3     300255.SZ   20211012  常山药业   8.39   7.26
4     688378.SH   20211012   奥来德  68.62  67.00
...         ...        ...   ...    ...    ...
4529  688257.SH   20211012  新锐股份   0.00   0.00
4530  688255.SH   20211012   凯尔达   0.00   0.00
4531  688211.SH   20211012  中科微至   0.00   0.00
4532  605567.SH   20211012  春雪食品   0.00   0.00
4533  605566.SH   20211012  福莱蒽特   0.00   0.00
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_bak_daily`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/bak_daily.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
