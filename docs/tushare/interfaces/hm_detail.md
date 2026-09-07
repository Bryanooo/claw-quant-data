# `hm_detail` — 游资每日明细

- 分类：股票数据/打板专题数据
- 功能：获取每日游资交易明细，数据开始于2022年8。游资分类名录，请点击 游资名录
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：用户积10000积分可调取使用，积分获取办法请参阅 积分获取办法 注：数据为当日部分数据，此处只未作为示例效果。
- 官方文档：[doc 312](https://tushare.pro/document/2?doc_id=312)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期(YYYYMMDD) |
| `ts_code` | str | N | 股票代码 |
| `hm_name` | str | N | 游资名称 |
| `start_date` | str | N | 开始日期(YYYYMMDD) |
| `end_date` | str | N | 结束日期(YYYYMMDD) |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | 股票代码 |
| `ts_name` | str | Y | 股票名称 |
| `buy_amount` | float | Y | 买入金额（元） |
| `sell_amount` | float | Y | 卖出金额（元） |
| `net_amount` | float | Y | 净买卖（元） |
| `hm_name` | str | Y | 游资名称 |
| `hm_orgs` | str | Y | 关联机构（一般为营业部或机构专用） |
| `tag` | str | N | 标签 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "hm_detail",
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

#获取单日全部明细
df = pro.hm_detail(trade_date='20230815')
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
