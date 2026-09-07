# `slb_len` — 转融资交易汇总

- 分类：股票数据/两融及转融通
- 功能：转融通融资汇总
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：2000积分每分钟请求200次，5000积分500次请求
- 官方文档：[doc 331](https://tushare.pro/document/2?doc_id=331)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/margin/margin.py:SlbLenCollector](../../../collectors/stock/margin/margin.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期（YYYYMMDD格式，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ob` | float | Y | 期初余额(亿元) |
| `auc_amount` | float | Y | 竞价成交金额(亿元) |
| `repo_amount` | float | Y | 再借成交金额(亿元) |
| `repay_amount` | float | Y | 偿还金额(亿元) |
| `cb` | float | Y | 期末余额(亿元) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "slb_len",
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

df = pro.slb_len(start_date='20240601', end_date='20240620')
```

## 实际返回示例（官方文档）

```text
trade_date    ob auc_amount repo_amount repay_amount     cb
0    20240620  1435.50       None        3.10         3.10  1435.50
1    20240619  1435.50       None        2.70         2.70  1435.50
2    20240618  1440.20       None       29.50        34.20  1435.50
3    20240617  1442.20       None        3.00         5.00  1440.20
4    20240614  1442.20       None        None         None  1442.20
5    20240613  1445.20       None        2.90         5.90  1442.20
6    20240612  1445.20       None        3.30         3.30  1445.20
7    20240611  1454.20       None        2.70        11.70  1445.20
8    20240607  1454.20       None        None         None  1454.20
9    20240606  1454.20       None       26.00        26.00  1454.20
10   20240605  1455.60       None        6.00         7.40  1454.20
11   20240604  1406.00      50.00        6.40         6.80  1455.60
12   20240603  1406.00       None        1.00         1.00  1406.00
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
