# `dc_member` — 板块成分

- 分类：股票数据/打板专题数据
- 功能：获取板块每日成分数据，可以根据概念板块代码和交易日期，获取历史成分
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积累6000积分可调取，具体请参阅 积分获取办法
- 官方文档：[doc 363](https://tushare.pro/document/2?doc_id=363)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/board/dc_member.py:DcMemberCollector](../../../collectors/stock/board/dc_member.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 板块指数代码 |
| `con_code` | str | N | 成分股票代码 |
| `trade_date` | str | N | 交易日期（YYYYMMDD格式） |
| `start_date` | str | N | 开始日期（YYYYMMDD格式） |
| `end_date` | str | N | 结束日期（YYYYMMDD格式） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | 概念代码 |
| `con_code` | str | Y | 成分代码 |
| `name` | str | Y | 成分股名称 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "dc_member",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取2025年1月2日的人形机器人概念板块成分列表
df = pro.dc_member(trade_date='20250102', ts_code='BK1184.DC')
```

## 实际返回示例（官方文档）

```text
trade_date  ts_code   con_code   name
0    20250102  BK1184.DC  002117.SZ   东港股份
1    20250102  BK1184.DC  603662.SH   柯力传感
2    20250102  BK1184.DC  688165.SH  埃夫特-U
3    20250102  BK1184.DC  300660.SZ   江苏雷利
4    20250102  BK1184.DC  873593.BJ   鼎智科技
..        ...        ...        ...    ...
59   20250102  BK1184.DC  002139.SZ   拓邦股份
60   20250102  BK1184.DC  301236.SZ   软通动力
61   20250102  BK1184.DC  601727.SH   上海电气
62   20250102  BK1184.DC  300432.SZ   富临精工
63   20250102  BK1184.DC  300843.SZ   胜蓝股份
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
