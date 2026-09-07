# `stk_high_shock` — 个股严重异常波动

- 分类：股票数据/参考数据
- 功能：根据证券交易所交易规则的有关规定，交易所每日发布股票交易严重异常波动情况
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：需要6000积分可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 452](https://tushare.pro/document/2?doc_id=452)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/reference/stk_high_shock.py](../../../collectors/stock/reference/stk_high_shock.py)、[collectors/stock/reference/stk_high_shock.py:StkHighShockCollector](../../../collectors/stock/reference/stk_high_shock.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码（可以通过stock_basic获取）示例:000001.SZ |
| `trade_date` | str | N | 交易日期（YYYYMMDD格式）示例:20260312 |
| `start_date` | str | N | 开始日期（YYYYMMDD格式）示例:20260312 |
| `end_date` | str | N | 结束日期（YYYYMMDD格式）示例:20260312 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | str | Y | 公告日期 |
| `name` | str | Y | 股票名称 |
| `trade_market` | str | Y | 交易所 |
| `reason` | str | Y | 异常说明 |
| `period` | str | Y | 异常期间 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stk_high_shock",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
# 导入sdk包
import tushare as ts

# 配置凭据token
ts.set_token('<--your-token-->')

# 初始化接口实例
pro = ts.pro_api()

#获取2026年3月12日的当日所有个股严重异常波动信息
df = pro.stk_high_shock(trade_date='20260312')

#获取股票”协鑫能科“2025年以来每个交易日的个股严重异常波动信息
df = pro.stk_high_shock(ts_code='002015.SZ', start_date='20250101', end_date='20251231')
```

## 实际返回示例（官方文档）

```text
ts_code  trade_date   name         trade_market                     reason                 period
0  301373.SZ  2026-03-10   凌玮科技          创业板  连续10个交易日内收盘价格涨幅偏离值累计达100%  2026-03-10-2026-03-24
1  300164.SZ  2026-03-03   通源石油          创业板  连续10个交易日内收盘价格涨幅偏离值累计达100%  2026-03-03-2026-03-17
2  001896.SZ  2026-02-27   豫能控股         深市主板  连续10个交易日内收盘价格涨幅偏离值累计达100%  2026-02-27-2026-03-13
3  000004.BJ  2026-02-25  *ST国华         深市主板    连续10个交易日内4次出现同负向异常波动的证券  2026-02-25-2026-03-11
4  300461.SZ  2026-02-25   田中精机          创业板  连续30个交易日内收盘价格涨幅偏离值累计达200%  2026-02-25-2026-03-11
5  603103.SH  2026-02-10   横店影视         沪市主板  连续10个交易日内收盘价格涨幅偏离值累计达100%  2026-02-10-2026-03-04
6  300912.SZ  2026-02-09   凯龙高科          创业板  连续10个交易日内收盘价格涨幅偏离值累计达100%  2026-02-09-2026-03-03
7  000711.SZ  2026-02-09   ST京蓝         深市主板    连续10个交易日内4次出现同正向异常波动的证券  2026-02-09-2026-03-03
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
