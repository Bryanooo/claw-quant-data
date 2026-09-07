# `repurchase` — 股票回购

- 分类：股票数据/参考数据
- 功能：获取上市公司回购股票数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 124](https://tushare.pro/document/2?doc_id=124)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/reference/repurchase.py](../../../collectors/stock/reference/repurchase.py)、[collectors/stock/reference/repurchase.py:RepurchaseCollector](../../../collectors/stock/reference/repurchase.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ann_date` | str | N | 公告日期（任意填参数，如果都不填，单次默认返回2000条） |
| `start_date` | str | N | 公告开始日期 |
| `end_date` | str | N | 公告结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `ann_date` | str | Y | 公告日期 |
| `end_date` | str | Y | 截止日期 |
| `proc` | str | Y | 进度 |
| `exp_date` | str | Y | 过期日期 |
| `vol` | float | Y | 回购数量 |
| `amount` | float | Y | 回购金额 |
| `high_limit` | float | Y | 回购最高价 |
| `low_limit` | float | Y | 回购最低价 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "repurchase",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "start_date": "20260730",
    "end_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.repurchase(ann_date='', start_date='20180101', end_date='20180510')

#取某日
df = pro.repurchase(ann_date='20181010')
```

## 实际返回示例（官方文档）

```text
ts_code  ann_date  end_date    proc  exp_date         vol        amount  \
0   300451.SZ  20181010  20181008      完成      None     51900.0  4.498500e+05
1   300396.SZ  20181010      None  股东大会通过  20191010         NaN  5.000000e+07
2   000813.SZ  20181010  20180930      实施      None  15450767.0  1.243010e+08
3   300451.SZ  20181010  20181008      完成      None      4500.0  3.708000e+04
4   002334.SZ  20181010  20181009      实施      None   7749553.0  3.826948e+07
5   600351.SH  20181010  20181010      实施      None   7035198.0  4.999188e+07
6   002104.SZ  20181010  20180930      实施      None    569100.0  3.584390e+06
7   603017.SH  20181010  20181009      实施      None   4418358.0  4.398425e+07
8   002511.SZ  20181010      None  股东大会通过  20190410         NaN  2.000000e+08
9   603180.SH  20181010  20181009      实施      None    315700.0  1.817800e+07
10  002567.SZ  20181010  20180930      实施      None   1743273.0  7.815226e+06


    high_limit  low_limit
0       12.350      8.240
1       21.000        NaN
2        8.400      7.800
3        8.240      8.240
4        6.060      4.370
5        7.490      6.850
6        6.352      6.160
7       10.600      9.080
8        9.500        NaN
9       59.860     55.060
10       4.600      4.370
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
