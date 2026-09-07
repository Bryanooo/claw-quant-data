# `fina_mainbz` — 主营业务构成

- 分类：股票数据/财务数据
- 功能：获得上市公司主营业务构成，分地区/产品/行业等方式。
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 ，单次最大提取100行，总量不限制，可循环获取。 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用fina_mainbz_vip接口（参数一致），需积攒5000积分。
- 官方文档：[doc 81](https://tushare.pro/document/2?doc_id=81)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（fina_mainbz_vip）；代码：[collectors/stock/finance/fina_mainbz.py](../../../collectors/stock/finance/fina_mainbz.py)、[collectors/stock/finance/fina_mainbz.py:FinaMainbzCollector](../../../collectors/stock/finance/fina_mainbz.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `period` | str | N | 报告期(每个季度最后一天的日期,比如20171231表示年报) |
| `type` | str | N | 类型：P-按产品 D-按地区 I-按行业（请输入大写字母） |
| `start_date` | str | N | 报告期开始日期 |
| `end_date` | str | N | 报告期结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | TS代码 |  |
| `end_date` | str | 报告期 |  |
| `bz_item` | str | 主营业务来源 |  |
| `bz_code` | str | 主营业务来源类型（P-按产品 D-按地区 I-按行业） |  |
| `bz_sales` | float | 主营业务收入(元) |  |
| `bz_profit` | float | 主营业务利润(元) |  |
| `bz_cost` | float | 主营业务成本(元) |  |
| `curr_type` | str | 货币代码（CNY） |  |
| `update_flag` | str | 是否更新 |  |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fina_mainbz",
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

df = pro.fina_mainbz(ts_code='000627.SZ', type='P')
```

## 实际返回示例（官方文档）

```text
ts_code  end_date    bz_item       bz_sales       bz_profit bz_cost curr_type
0  000627.SZ  20171231    其他产品      1.847507e+08      None    None       CNY
1  000627.SZ  20171231    其他主营业务  1.847507e+08      None    None       CNY
2  000627.SZ  20171231    聚丙烯        6.629111e+07      None    None       CNY
3  000627.SZ  20171231    原料药产品    2.685909e+08      None    None       CNY
4  000627.SZ  20171231    保险业务      5.288595e+10      None    None       CNY
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
