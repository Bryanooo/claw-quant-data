# `fut_holding` — 每日成交持仓排名

- 分类：期货数据
- 功能：获取每日成交持仓排名数据，注意"上期所"涵盖"上海国际能源交易中心"合约数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 139](https://tushare.pro/document/2?doc_id=139)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期 （trade_date/symbol至少输入一个参数） |
| `symbol` | str | N | 合约或产品代码 |
| `start_date` | str | N | 开始日期(YYYYMMDD格式，下同) |
| `end_date` | str | N | 结束日期 |
| `exchange` | str | N | 交易所代码 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `symbol` | str | Y | 合约代码或类型 |
| `broker` | str | Y | 期货公司会员简称 |
| `vol` | int | Y | 成交量 |
| `vol_chg` | int | Y | 成交量变化 |
| `long_hld` | int | Y | 持买仓量 |
| `long_chg` | int | Y | 持买仓量变化 |
| `short_hld` | int | Y | 持卖仓量 |
| `short_chg` | int | Y | 持卖仓量变化 |
| `exchange` | str | N | 交易所 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fut_holding",
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

df = pro.fut_holding(trade_date='20181113', symbol='C1905', exchange='DCE')
```

## 实际返回示例（官方文档）

```text
trade_date symbol  broker       vol    vol_chg  long_hld    long_chg  \
0    20181113      C    东证期货   37161.0   -6435.0   15432.0    1837.0
1    20181113      C    中信建投   12293.0   -1737.0       NaN       NaN
2    20181113      C    中信期货   31284.0   -4508.0   31672.0     102.0
3    20181113      C    中粮期货   12331.0   -5430.0   45350.0    3705.0
4    20181113      C    中融汇信       NaN       NaN       NaN       NaN
5    20181113      C    中金期货       NaN       NaN   18321.0    1491.0
6    20181113      C    五矿经易       NaN       NaN   17828.0    1729.0
7    20181113      C    倍特期货       NaN       NaN   15271.0     123.0
8    20181113      C    光大期货   72795.0  -29668.0   36988.0     752.0
9    20181113      C    兴证期货   21058.0   -4901.0   24372.0   -8720.0
10   20181113      C    北京首创       NaN       NaN       NaN       NaN
11   20181113      C    华安期货   12550.0    -919.0       NaN       NaN
12   20181113      C    华泰期货   16339.0    4783.0   30374.0    -806.0
13   20181113      C    国富期货       NaN       NaN       NaN       NaN
14   20181113      C    国投安信   49251.0  -43610.0   84537.0    4253.0
15   20181113      C    国泰君安   13095.0   -3810.0   16019.0      88.0
16   20181113      C    天风期货       NaN       NaN       NaN       NaN
17   20181113      C    安粮期货       NaN       NaN   15294.0    1651.0
18   20181113      C    山西三立       NaN       NaN   14686.0     457.0
19   20181113      C    广发期货   15539.0  -10927.0       NaN       NaN
20   20181113      C    广州金控   11303.0    1810.0       NaN       NaN

    short_hld  short_chg
0     14281.0     -384.0
1         NaN        NaN
2     15634.0    -6336.0
3     70184.0    -2658.0
4     12279.0      467.0
5         NaN        NaN
6         NaN        NaN
7         NaN        NaN
8     42506.0     -279.0
9         NaN        NaN
10    11456.0    -4974.0
11        NaN        NaN
12        NaN        NaN
13    10935.0      288.0
14   105797.0     7326.0
15    15811.0    -1489.0
16    33336.0      567.0
17        NaN        NaN
18        NaN        NaN
19        NaN        NaN
20        NaN        NaN
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fut_holding`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fut_holding.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
