# `dividend` — 分红送股

- 分类：股票数据/财务数据
- 功能：分红送股数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 103](https://tushare.pro/document/2?doc_id=103)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/finance/dividend.py](../../../collectors/stock/finance/dividend.py)、[collectors/stock/finance/dividend.py:DividendCollector](../../../collectors/stock/finance/dividend.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS代码 |
| `ann_date` | str | N | 公告日 |
| `record_date` | str | N | 股权登记日期 |
| `ex_date` | str | N | 除权除息日 |
| `imp_ann_date` | str | N | 实施公告日 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `end_date` | str | Y | 分红年度 |
| `ann_date` | str | Y | 公告日(预案，决案) |
| `div_proc` | str | Y | 实施进度 |
| `stk_div` | float | Y | 每股送转 |
| `stk_bo_rate` | float | Y | 每股送股比例 |
| `stk_co_rate` | float | Y | 每股转增比例 |
| `cash_div` | float | Y | 每股分红（税后） |
| `cash_div_tax` | float | Y | 每股分红（税前） |
| `record_date` | str | Y | 股权登记日 |
| `ex_date` | str | Y | 除权除息日 |
| `pay_date` | str | Y | 派息日 |
| `div_listdate` | str | Y | 红股上市日 |
| `imp_ann_date` | str | Y | 实施公告日 |
| `base_date` | str | N | 基准日 |
| `base_share` | float | N | 基准股本（万） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "dividend",
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

df = pro.dividend(ts_code='600848.SH', fields='ts_code,div_proc,stk_div,record_date,ex_date')
```

## 实际返回示例（官方文档）

```text
ts_code div_proc  stk_div record_date   ex_date
    0  600848.SH       实施     0.10    19950606  19950607
    1  600848.SH       实施     0.10    19970707  19970708
    2  600848.SH       实施     0.15    19960701  19960702
    3  600848.SH       实施     0.10    19980706  19980707
    4  600848.SH       预案     0.00        None      None
    5  600848.SH       实施     0.00    20180522  20180523
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
