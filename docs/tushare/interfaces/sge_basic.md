# `sge_basic` — 黄金现货基础信息

- 分类：现货数据
- 功能：获取上海黄金交易所现货合约基础信息
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积5000积分可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 284](https://tushare.pro/document/2?doc_id=284)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/sge/sge_basic.py:SgeBasicCollector](../../../collectors/sge/sge_basic.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 合约代码 （支持多个，逗号分隔，不输入为获取全部） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 品种代码 |
| `ts_name` | str | Y | 品种名称 |
| `trade_type` | str | Y | 交易类型 |
| `t_unit` | float | Y | 交易单位(克/手) |
| `p_unit` | float | Y | 报价单位 |
| `min_change` | float | Y | 最小变动价位 |
| `price_limit` | float | Y | 每日价格最大波动限制 |
| `min_vol` | int | Y | 最小单笔报价量(手) |
| `max_vol` | int | Y | 最大单笔报价量(手) |
| `trade_mode` | str | Y | 交易期限 |
| `margin_rate` | float | Y | 保证金比例 |
| `liq_rate` | float | Y | 违约金比例(%) |
| `trade_time` | str | Y | 交易时间 |
| `list_date` | str | Y | 上市日期 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "sge_basic",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "Au99.99.SGE"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.sge_basic()
```

## 实际返回示例（官方文档）

```text
ts_code    ts_name  min_vol  max_vol       trade_time
0    Au99.95     黄金9995        1      500     白天：9:00至15:30，夜间:19:50 至次日 02:30
1    Au99.99     黄金9999        1    50000    白天：9:00至15:30，夜间:19:50 至次日 02:30
2    Au(T+D)       黄金延期        1      200     上午:9:00 至 11:30，下午 ...
3    Pt99.95     铂金9995        1     1000       白天：9:00至15:30，夜间:19:50 至次日 02:30
4    Ag(T+D)       白银延期        1     2000    上午:9:00 至 11:30，下午:...
5     Au100g     100克金条        1     1000     白天：9:00至15:30，夜间:19:50 至次日 02:30
6   Au(T+N1)     黄金T+N1        1     2000      上午:9:00 至 11:30，下午:13:30 至 ...
7   Au(T+N2)     黄金T+N2        1     2000      上午:9:00 至 11:30，下午:13:30 至 ...
8   mAu(T+D)     迷你黄金延期        1     2000    上午:9:00 至 11:30，下午:13:30 至 ...
9   iAu99.99  国际板黄金9999        1    50000    白天：9:00至15:30，夜间:19:50 至次日 02:30
10    PGC30g    熊猫金币30克        1     1000     白天：9:00至15:30，夜间：20:00至次日02:30
11  NYAuTN06  沪纽金AuTN06        1     2000   白天：9:00至15:30，夜间:19:50 至次日 02:30
12  NYAuTN12  沪纽金AuTN12        1     2000   白天：9:00至15:30，夜间:19:50 至次日 02:30
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
