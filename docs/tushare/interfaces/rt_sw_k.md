# `rt_sw_k` — 申万实时行情

- 分类：指数专题
- 功能：获取申万行业指数的最新截面数据
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：本接口是单独开权限的数据，单独申请权限请参考 权限列表
- 官方文档：[doc 417](https://tushare.pro/document/2?doc_id=417)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 指数代码，如: 801005.SI；可以是逗号隔开的多个，如: 801005.SI,801001.SI |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 指数代码 |
| `name` | str | Y | 指数名称 |
| `trade_time` | str | Y | 交易时间 |
| `close` | float | Y | 现价 |
| `pre_close` | float | Y | 昨收 |
| `high` | float | Y | 最高价 |
| `open` | float | Y | 开盘价 |
| `low` | float | Y | 最低价 |
| `vol` | float | Y | 成交量（股） |
| `amount` | float | Y | 成交金额（元） |
| `pct_change` | float | Y | 增长率 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "rt_sw_k",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

# 一次性提取全部申万指数实时数据
df = pro.rt_sw_k()

# 按ts_code提取行情数据，例如提取801053.SI(贵金属) 实时行情
df = pro.rt_sw_k(ts_code='801053.SI')
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
