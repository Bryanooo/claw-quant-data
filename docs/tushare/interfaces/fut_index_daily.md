# `fut_index_daily` — 南华期货指数日线行情

- 分类：期货数据
- 功能：获取南华指数每日行情，指数行情也可以通过 通用行情接口 获取数据．
- Token 权限：**有权限**（权限层已通过，接口进入参数校验）
- 官方权限要求：用户需要累积2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 468](https://tushare.pro/document/2?doc_id=468)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 指数代码（南华期货指数以 .NH 结尾，具体请参考本文最下方） |
| `trade_date` | str | N | 交易日期 （日期格式：YYYYMMDD，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | None | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS指数代码 |
| `trade_date` | str | Y | 交易日 |
| `close` | float | Y | 收盘点位 |
| `open` | float | Y | 开盘点位 |
| `high` | float | Y | 最高点位 |
| `low` | float | Y | 最低点位 |
| `pre_close` | float | Y | 昨日收盘点 |
| `change` | float | Y | 涨跌点 |
| `pct_chg` | float | Y | 涨跌幅 |
| `vol` | float | Y | 成交量（手） |
| `amount` | float | Y | 成交额（千元） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fut_index_daily",
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

#获取南华沪铜指数
df = pro.fut_index_daily(ts_code='CU.NH', start_date='20180101', end_date='20181201')
```

## 实际返回示例（官方文档）

```text
ts_code trade_date     close      open      high       low  pre_close  \
0     CU.NH   20181130  3928.773  3918.501  3928.773  3907.438   3916.130
1     CU.NH   20181129  3916.130  3891.634  3936.675  3880.572   3894.005
2     CU.NH   20181128  3894.005  3863.978  3895.585  3841.853   3862.398
3     CU.NH   20181127  3862.398  3905.068  3906.648  3844.224   3895.585
4     CU.NH   20181126  3895.585  3895.585  3907.438  3875.831   3903.487
5     CU.NH   20181123  3903.487  3915.340  3937.465  3897.956   3916.920
6     CU.NH   20181122  3916.920  3919.291  3927.983  3892.425   3904.277
7     CU.NH   20181121  3904.277  3931.143  3950.898  3851.335   3917.710
8     CU.NH   20181120  3917.710  3939.045  3953.268  3914.550   3933.514
9     CU.NH   20181119  3933.514  3909.018  3944.577  3903.487   3917.710
10    CU.NH   20181116  3917.710  3916.130  3932.724  3904.277   3912.969
11    CU.NH   20181115  3912.969  3869.509  3917.710  3865.559   3857.657
12    CU.NH   20181114  3857.657  3878.992  3899.536  3849.755   3879.782
13    CU.NH   20181113  3879.782  3866.349  3882.152  3845.804   3865.559
14    CU.NH   20181112  3865.559  3877.411  3884.523  3853.706   3886.103
15    CU.NH   20181109  3886.103  3889.264  3916.130  3877.411   3901.117
16    CU.NH   20181108  3901.117  3921.661  3926.402  3896.376   3909.018
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fut_index_daily`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fut_index_daily.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
