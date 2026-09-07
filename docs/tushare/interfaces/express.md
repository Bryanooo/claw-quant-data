# `express` — 业绩快报

- 分类：股票数据/财务数据
- 功能：获取上市公司业绩快报
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用express_vip接口（参数一致），需积攒5000积分。
- 官方文档：[doc 46](https://tushare.pro/document/2?doc_id=46)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（express_vip）；代码：[collectors/stock/finance/express.py:ExpressCollector](../../../collectors/stock/finance/express.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `ann_date` | str | N | 公告日期 |
| `start_date` | str | N | 公告开始日期 |
| `end_date` | str | N | 公告结束日期 |
| `period` | str | N | 报告期(每个季度最后一天的日期,比如20171231表示年报，20170630半年报，20170930三季报) |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS股票代码 |
| `ann_date` | str | Y | 公告日期 |
| `end_date` | str | Y | 报告期 |
| `revenue` | float | Y | 营业收入(元) |
| `operate_profit` | float | Y | 营业利润(元) |
| `total_profit` | float | Y | 利润总额(元) |
| `n_income` | float | Y | 净利润(元) |
| `total_assets` | float | Y | 总资产(元) |
| `total_hldr_eqy_exc_min_int` | float | Y | 股东权益合计(不含少数股东权益)(元) |
| `diluted_eps` | float | Y | 每股收益(摊薄)(元) |
| `diluted_roe` | float | Y | 净资产收益率(摊薄)(%) |
| `yoy_net_profit` | float | Y | 去年同期修正后净利润 |
| `bps` | float | Y | 每股净资产 |
| `yoy_sales` | float | N | 同比增长率:营业收入 |
| `yoy_op` | float | N | 同比增长率:营业利润 |
| `yoy_tp` | float | N | 同比增长率:利润总额 |
| `yoy_dedu_np` | float | N | 同比增长率:归属母公司股东的净利润 |
| `yoy_eps` | float | N | 同比增长率:基本每股收益 |
| `yoy_roe` | float | N | 同比增减:加权平均净资产收益率 |
| `growth_assets` | float | N | 比年初增长率:总资产 |
| `yoy_equity` | float | N | 比年初增长率:归属母公司的股东权益 |
| `growth_bps` | float | N | 比年初增长率:归属于母公司股东的每股净资产 |
| `or_last_year` | float | N | 去年同期营业收入 |
| `op_last_year` | float | N | 去年同期营业利润 |
| `tp_last_year` | float | N | 去年同期利润总额 |
| `np_last_year` | float | N | 去年同期净利润 |
| `eps_last_year` | float | N | 去年同期每股收益 |
| `open_net_assets` | float | N | 期初净资产 |
| `open_bps` | float | N | 期初每股净资产 |
| `perf_summary` | str | N | 业绩简要说明 |
| `is_audit` | int | N | 是否审计： 1是 0否 |
| `remark` | str | N | 备注 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "express",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SZ"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

pro.express(ts_code='600000.SH', start_date='20180101', end_date='20180701', fields='ts_code,ann_date,end_date,revenue,operate_profit,total_profit,n_income,total_assets')
```

## 实际返回示例（官方文档）

```text
ts_code  ann_date  end_date       revenue  operate_profit  total_profit      n_income  total_assets  \
0  603535.SH  20180411  20180331  2.064659e+08    3.345047e+07  3.340047e+07  2.672643e+07  1.682111e+09
1  603535.SH  20180208  20171231  1.034262e+09    1.323373e+08  1.440493e+08  1.188325e+08  1.710466e+09
2  603535.SH  20171016  20170930  7.064117e+08    9.509520e+07  9.931530e+07  8.202480e+07  1.672986e+09
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
