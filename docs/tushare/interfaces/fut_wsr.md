# `fut_wsr` — 仓单日报

- 分类：期货数据
- 功能：获取仓单日报数据，了解各仓库/厂库的仓单变化
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 140](https://tushare.pro/document/2?doc_id=140)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期 |
| `symbol` | str | N | 产品代码 |
| `start_date` | str | N | 开始日期(YYYYMMDD格式，下同) |
| `end_date` | str | N | 结束日期 |
| `exchange` | str | N | 交易所代码 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `symbol` | str | Y | 产品代码 |
| `fut_name` | str | Y | 产品名称 |
| `warehouse` | str | Y | 仓库名称 |
| `wh_id` | str | N | 仓库编号 |
| `pre_vol` | int | Y | 昨日仓单量 |
| `vol` | int | Y | 今日仓单量 |
| `vol_chg` | int | Y | 增减量 |
| `area` | str | N | 地区 |
| `year` | str | N | 年度 |
| `grade` | str | N | 等级 |
| `brand` | str | N | 品牌 |
| `place` | str | N | 产地 |
| `pd` | int | N | 升贴水 |
| `is_ct` | str | N | 是否折算仓单 |
| `unit` | str | Y | 单位 |
| `exchange` | str | N | 交易所 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fut_wsr",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api('your token')

df = pro.fut_wsr(trade_date='20181113', symbol='ZN')
```

## 实际返回示例（官方文档）

```text
trade_date symbol fut_name    warehouse  pre_vol   vol  vol_chg unit
0    20181113     ZN        锌      上海裕强     4960  4960        0    吨
1    20181113     ZN        锌      上港物流      702   702        0    吨
2    20181113     ZN        锌    上港物流苏州        0     0        0    吨
3    20181113     ZN        锌      中储吴淞        0     0        0    吨
4    20181113     ZN        锌      中储大场        0     0        0    吨
5    20181113     ZN        锌      中储晟世        0     0        0    吨
6    20181113     ZN        锌      中金圣源      428   353      -75    吨
7    20181113     ZN        锌      全胜物流     2882  2882        0    吨
8    20181113     ZN        锌      南储仓储       25    25        0    吨
9    20181113     ZN        锌      同盛松江        0     0        0    吨
10   20181113     ZN        锌    国储837处        0     0        0    吨
11   20181113     ZN        锌      国储天威        0     0        0    吨
12   20181113     ZN        锌    国能物流常州      200   200        0    吨
13   20181113     ZN        锌   外运华东张华浜        0     0        0    吨
14   20181113     ZN        锌     宁波九龙仓        0     0        0    吨
15   20181113     ZN        锌  广储830三水西        0     0        0    吨
16   20181113     ZN        锌      康运萧山        0     0        0    吨
17   20181113     ZN        锌      无锡国联        0     0        0    吨
18   20181113     ZN        锌      期晟公司      449   226     -223    吨
19   20181113     ZN        锌      浙江康运       25    25        0    吨
20   20181113     ZN        锌     百金汇物流        0     0        0    吨
21   20181113     ZN        锌      裕强闵行        0     0        0    吨
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fut_wsr`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fut_wsr.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
