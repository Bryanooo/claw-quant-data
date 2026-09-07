# `broker_recommend` — 券商每月荐股

- 分类：股票数据/特色数据
- 功能：获取券商月度金股，一般1日~3日内更新当月数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：积分达到6000即可调用，具体请参阅 积分获取办法
- 官方文档：[doc 267](https://tushare.pro/document/2?doc_id=267)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/extra/broker_recommend.py:BrokerRecommendCollector](../../../collectors/stock/extra/broker_recommend.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `month` | str | Y | 月度（YYYYMM） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `month` | str | Y | 月度 |
| `broker` | str | Y | 券商 |
| `ts_code` | str | Y | 股票代码 |
| `name` | str | Y | 股票简称 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "broker_recommend",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "month": "202608"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取查询月份券商金股
df = pro.broker_recommend(month='202106')
```

## 实际返回示例（官方文档）

```text
month broker    ts_code  name
0    202106   东兴证券  000066.SZ  中国长城
1    202106   东兴证券  000708.SZ  中信特钢
2    202106   东兴证券  002304.SZ  洋河股份
3    202106   东兴证券  003816.SZ  中国广核
4    202106   东兴证券  300196.SZ  长海股份
..      ...    ...        ...   ...
263  202106   长城证券  600096.SH   云天化
264  202106   长城证券  600809.SH  山西汾酒
265  202106   长城证券  603596.SH   伯特利
266  202106   长城证券  603885.SH  吉祥航空
267  202106   长城证券  605068.SH  明新旭腾
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
