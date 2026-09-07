# `fut_trade_cal` — 交易日历

- 分类：期货数据
- 功能：获取各大期货交易所交易日历数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：需2000积分才可以提取数据
- 官方文档：[doc 467](https://tushare.pro/document/2?doc_id=467)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `exchange` | str | N | 交易所 SHFE 上期所 DCE 大商所 CFFEX中金所 CZCE郑商所 INE上海国际能源交易所 |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `is_open` | int | N | 是否交易 0休市 1交易 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `exchange` | str | Y | 交易所 同参数部分描述 |
| `cal_date` | str | Y | 日历日期 |
| `is_open` | int | Y | 是否交易 0休市 1交易 |
| `pretrade_date` | str | N | 上一个交易日 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fut_trade_cal",
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
pro = ts.pro_api('your token')


df = pro.fut_trade_cal(exchange='DCE', start_date='20180101', end_date='20181231')
```

## 实际返回示例（官方文档）

```text
exchange  cal_date  is_open
0        DCE  20180101        0
1        DCE  20180102        1
2        DCE  20180103        1
3        DCE  20180104        1
4        DCE  20180105        1
5        DCE  20180106        0
6        DCE  20180107        0
7        DCE  20180108        1
8        DCE  20180109        1
9        DCE  20180110        1
10       DCE  20180111        1
11       DCE  20180112        1
12       DCE  20180113        0
13       DCE  20180114        0
14       DCE  20180115        1
15       DCE  20180116        1
16       DCE  20180117        1
17       DCE  20180118        1
18       DCE  20180119        1
19       DCE  20180120        0
20       DCE  20180121        0
21       DCE  20180122        1
22       DCE  20180123        1
23       DCE  20180124        1
24       DCE  20180125        1
25       DCE  20180126        1
26       DCE  20180127        0
27       DCE  20180128        0
28       DCE  20180129        1
29       DCE  20180130        1
..       ...       ...      ...
335      DCE  20181202        0
336      DCE  20181203        1
337      DCE  20181204        1
338      DCE  20181205        1
339      DCE  20181206        1
340      DCE  20181207        1
341      DCE  20181208        0
342      DCE  20181209        0
343      DCE  20181210        1
344      DCE  20181211        1
345      DCE  20181212        1
346      DCE  20181213        1
347      DCE  20181214        1
348      DCE  20181215        0
349      DCE  20181216        0
350      DCE  20181217        1
351      DCE  20181218        1
352      DCE  20181219        1
353      DCE  20181220        1
354      DCE  20181221        1
355      DCE  20181222        0
356      DCE  20181223        0
357      DCE  20181224        1
358      DCE  20181225        1
359      DCE  20181226        1
360      DCE  20181227        1
361      DCE  20181228        1
362      DCE  20181229        0
363      DCE  20181230        0
364      DCE  20181231        1
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fut_trade_cal`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fut_trade_cal.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
