# `rt_fut_min_daily` — 期货实时分钟行情

- 分类：期货数据
- 功能：获取全市场期货合约实时分钟数据，支持1min/5min/15min/30min/60min行情，提供Python SDK、 http Restful API和websocket三种方式，如果需要主力合约分钟，请先通过主力 mapping 接口获取对应的合约代码后提取分钟。
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：需单独开权限，正式权限请参阅 权限说明 。 rt_fut_min输入参数 名称 类型 必选 描述 ts_code str Y 股票代码，e.g.CU2310.SHF，支持多个合约（逗号分隔） freq str Y 分钟频度（1MIN/5MIN/15MIN/30MIN/60MIN） 同时提供当日开市以来所有历史分钟（即：分钟快照回放），接口名：rt_fut_min_daily，只支持一个个合约提取。 rt_fut_min_daily输入参数 名称 类型 必选 描述 ts_code str Y 股票代码，e.g.CU2310.SHF，仅支持一次一个合约的回放 freq str Y 分钟频度（1MIN/5MIN/15MIN/30MIN/60MIN） date_str str N 回放日期（格式：YYYY-MM-DD，默认为交易当日，支持回溯一天） freq参数说明 freq 说明 1MIN 1分钟 5MIN 5分钟 15MIN 15分钟 30MIN 30分钟 60MIN 60分钟
- 官方文档：[doc 340](https://tushare.pro/document/2?doc_id=340)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码，e.g.CU2310.SHF，支持多个合约（逗号分隔） |
| `freq` | str | Y | 分钟频度（1MIN/5MIN/15MIN/30MIN/60MIN） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码，e.g.CU2310.SHF，仅支持一次一个合约的回放 |
| `freq` | str | Y | 分钟频度（1MIN/5MIN/15MIN/30MIN/60MIN） |
| `date_str` | str | N | 回放日期（格式：YYYY-MM-DD，默认为交易当日，支持回溯一天） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "rt_fut_min_daily",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "CU.SHF",
    "freq": "D"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

#单个合约
df = pro.df = pro.rt_fut_min(ts_code='CU2501.SHF', freq='1MIN')

#多个合约
df = pro.df = pro.rt_fut_min(ts_code='CU2501.SHF,CU2502.SHF', freq='1MIN')
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
