# `rt_idx_min_daily` — A股实时分钟

- 分类：指数专题
- 功能：获取交易所指数实时分钟数据，包括1~60min
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：正式权限请参阅 权限说明 注：支持股票当日开盘以来的所有历史分钟数据提取，接口名：rt_idx_min_daily（仅支持一个个指数提取，不同同时提取多个），可以 在线开通 权限。
- 官方文档：[doc 420](https://tushare.pro/document/2?doc_id=420)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `freq` | str | Y | 1MIN,5MIN,15MIN,30MIN,60MIN （大写） |
| `ts_code` | str | Y | 支持单个和多个：000001.SH 或者 000001.SH,399300.SZ |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `time` | None | Y | 交易时间 |
| `open` | float | Y | 开盘价 |
| `close` | float | Y | 收盘价 |
| `high` | float | Y | 最高价 |
| `low` | float | Y | 最低价 |
| `vol` | float | Y | 成交量(股） |
| `amount` | float | Y | 成交额（元） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "rt_idx_min_daily",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "freq": "D",
    "ts_code": "000001.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

#获取上证综指000001.SH的实时分钟数据
df = pro.rt_idx_min(ts_code='000001.SH', freq='1MIN')


#获取沪深300指数399300.SZ当日开盘以来的所有1分钟数据
df = pro.rt_idx_min_daily(ts_code='399300.SZ', freq='1MIN')
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
