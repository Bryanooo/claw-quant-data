# `index_dailybasic` — 大盘指数每日指标

- 分类：指数专题
- 功能：目前只提供上证综指，深证成指，上证50，中证500，中小板指，创业板指的每日指标数据 数据来源：Tushare社区统计计算 数据历史：从2004年1月开始提供 数据权限：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 128](https://tushare.pro/document/2?doc_id=128)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/index/dailybasic.py:IndexDailybasicCollector](../../../collectors/index/dailybasic.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期 （格式：YYYYMMDD，比如20181018，下同） |
| `ts_code` | str | N | TS代码 |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `trade_date` | str | Y | 交易日期 |
| `total_mv` | float | Y | 当日总市值（元） |
| `float_mv` | float | Y | 当日流通市值（元） |
| `total_share` | float | Y | 当日总股本（股） |
| `float_share` | float | Y | 当日流通股本（股） |
| `free_share` | float | Y | 当日自由流通股本（股） |
| `turnover_rate` | float | Y | 换手率 |
| `turnover_rate_f` | float | Y | 换手率(基于自由流通股本) |
| `pe` | float | Y | 市盈率 |
| `pe_ttm` | float | Y | 市盈率TTM |
| `pb` | float | Y | 市净率 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "index_dailybasic",
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

df = pro.index_dailybasic(trade_date='20181018', fields='ts_code,trade_date,turnover_rate,pe')
```

## 实际返回示例（官方文档）

```text
ts_code  trade_date  turnover_rate     pe
0  000001.SH   20181018           0.38  11.92
1  000300.SH   20181018           0.27  11.17
2  000905.SH   20181018           0.82  18.03
3  399001.SZ   20181018           0.88  17.48
4  399005.SZ   20181018           0.85  21.43
5  399006.SZ   20181018           1.50  29.56
6  399016.SZ   20181018           1.06  18.86
7  399300.SZ   20181018           0.27  11.17
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
