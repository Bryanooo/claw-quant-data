# `daily_info` — 市场交易统计

- 分类：指数专题
- 功能：获取交易所股票交易统计，包括各板块明细
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积600积分可调取， 频次有限制，积分越高每分钟调取频次越高，5000积分以上频次相对较高，积分获取方法请参阅 积分获取办法
- 官方文档：[doc 215](https://tushare.pro/document/2?doc_id=215)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期（YYYYMMDD格式，下同） |
| `ts_code` | str | N | 板块代码（请参阅下方列表） |
| `exchange` | str | N | 股票市场（SH上交所 SZ深交所） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `fields` | str | N | 指定提取字段 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | 市场代码 |
| `ts_name` | str | Y | 市场名称 |
| `com_count` | int | Y | 挂牌数 |
| `total_share` | float | Y | 总股本（亿股） |
| `float_share` | float | Y | 流通股本（亿股） |
| `total_mv` | float | Y | 总市值（亿元） |
| `float_mv` | float | Y | 流通市值（亿元） |
| `amount` | float | Y | 交易金额（亿元） |
| `vol` | float | Y | 成交量（亿股） |
| `trans_count` | int | Y | 成交笔数（万笔） |
| `pe` | float | Y | 平均市盈率 |
| `tr` | float | Y | 换手率（％），注：深交所暂无此列 |
| `exchange` | str | Y | 交易所（SH上交所 SZ深交所） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "daily_info",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取深圳市场20200320各板块交易数据
df = pro.daily_info(trade_date='20200320', exchange='SZ')

#获取深圳和上海市场20200320各板块交易指定字段的数据
df = pro.daily_info(trade_date='20200320', exchange='SZ,SH', fields='trade_date,ts_name,pe')
```

## 实际返回示例（官方文档）

```text
trade_date    ts_code ts_name  com_count  total_share  float_share  \
0   20200320     SZ_GME     创业板        802      4124.04      3159.24
1   20200320    SZ_MAIN    深市主板        470      8177.40      7176.03
2   20200320  SZ_MARKET    深圳市场       2220     21657.12     17674.90
3   20200320     SZ_SME   中小企业板        948      9355.67      7339.62

    total_mv   float_mv   amount     vol  trans_count     pe    tr exchange
0   66494.71   44955.24  1475.76   99.65        830.0  50.37   NaN       SZ
1   70732.59   62551.44   961.92  102.30        554.0  16.12   NaN       SZ
2  236813.99  184009.16  4363.01     NaN          NaN  25.46  2.18       SZ
3   99586.67   76502.47  1925.32  179.21       1208.0  27.74   NaN       SZ
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_daily_info`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/daily_info.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
