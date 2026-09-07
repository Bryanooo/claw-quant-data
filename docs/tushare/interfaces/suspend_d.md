# `suspend_d` — 每日停复牌信息

- 分类：股票数据/行情数据
- 功能：按日期方式获取股票每日停复牌信息
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 214](https://tushare.pro/document/2?doc_id=214)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/market/suspend_d.py:SuspendDCollector](../../../collectors/stock/market/suspend_d.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码(可输入多值) |
| `trade_date` | str | N | 交易日日期 |
| `start_date` | str | N | 停复牌查询开始日期 |
| `end_date` | str | N | 停复牌查询结束日期 |
| `suspend_type` | str | N | 停复牌类型：S-停牌,R-复牌 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `trade_date` | str | Y | 停复牌日期（覆盖从停牌到覆盖期间的连续日期） |
| `suspend_timing` | str | Y | 日内停牌时间段（日内停牌才有值，否则为空值） |
| `suspend_type` | str | Y | 停复牌类型：S-停牌，R-复牌 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "suspend_d",
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

#提取2020-03-12的停牌股票
df = pro.suspend_d(suspend_type='S', trade_date='20200312')
```

## 实际返回示例（官方文档）

```text
ts_code suspend_type trade_date suspend_timing
0   000029.SZ            S     20200312           None
1   000502.SZ            S     20200312           None
2   000939.SZ            S     20200312           None
3   000977.SZ            S     20200312           None
4   000995.SZ            S     20200312           None
5   002260.SZ            S     20200312           None
6   002450.SZ            S     20200312           None
7   002604.SZ            S     20200312           None
8   300028.SZ            S     20200312           None
9   300104.SZ            S     20200312           None
10  300216.SZ            S     20200312           None
11  300592.SZ            S     20200312           None
12  300819.SZ            S     20200312    09:30-10:00
13  300821.SZ            S     20200312    09:30-10:00
14  600074.SH            S     20200312           None
15  600145.SH            S     20200312           None
16  600228.SH            S     20200312           None
17  600310.SH            S     20200312           None
18  600610.SH            S     20200312           None
19  600745.SH            S     20200312           None
20  600766.SH            S     20200312           None
21  600891.SH            S     20200312           None
22  601127.SH            S     20200312           None
23  601162.SH            S     20200312           None
24  603002.SH            S     20200312           None
25  603399.SH            S     20200312           None
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
