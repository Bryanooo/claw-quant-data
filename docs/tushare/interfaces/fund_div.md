# `fund_div` — 公募基金分红

- 分类：公募基金
- 功能：获取公募基金分红数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少400积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 120](https://tushare.pro/document/2?doc_id=120)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ann_date` | str | N | 公告日（以下参数四选一） |
| `ex_date` | str | N | 除息日 |
| `pay_date` | str | N | 派息日 |
| `ts_code` | str | N | 基金代码 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `ann_date` | str | Y | 公告日期 |
| `imp_anndate` | str | Y | 分红实施公告日 |
| `base_date` | str | Y | 分配收益基准日 |
| `div_proc` | str | Y | 方案进度 |
| `record_date` | str | Y | 权益登记日 |
| `ex_date` | str | Y | 除息日 |
| `pay_date` | str | Y | 派息日 |
| `earpay_date` | str | Y | 收益支付日 |
| `net_ex_date` | str | Y | 净值除权日 |
| `div_cash` | float | Y | 每股派息(元) |
| `base_unit` | float | Y | 基准基金份额(万份) |
| `ear_distr` | float | Y | 可分配收益(元) |
| `ear_amount` | float | Y | 收益分配金额(元) |
| `account_date` | str | Y | 红利再投资到账日 |
| `base_year` | str | Y | 份额基准年度 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fund_div",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "510300.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.fund_div(ann_date='20181018')
```

## 实际返回示例（官方文档）

```text
ts_code  ann_date imp_anndate base_date div_proc record_date   ex_date  \
0  161618.OF  20181018    20181018  20180928       实施    20181022  20181022
1  161619.OF  20181018    20181018  20180928       实施    20181022  20181022
2  005485.OF  20181018    20181018  20181015       实施    20181022  20181022
3  519330.OF  20181018    20181018  20181012       实施    20181022  20181022
4  519331.OF  20181018    20181018  20181012       实施    20181022  20181022
5  164702.SZ  20181018    20181018  20180930       实施    20181022  20181023
6  005068.OF  20181018    20181018  20181016       实施    20181022  20181022
7  519953.OF  20181018    20181018  20181016       实施    20181022  20181022

   pay_date earpay_date net_ex_date  div_cash    base_unit    ear_distr  \
0  20181024        None        None    0.0170   14982.2740   5018943.83
1  20181024        None        None    0.0150    2894.7015    823800.02
2  20181024        None        None    0.0180  101004.4450  18689411.19
3  20181024        None        None    0.0060  219742.3332  65922699.95
4  20181024        None        None    0.0050       4.8656      1216.42
5  20181024        None        None    0.0150   41287.3653   8058271.35
6  20181024        None        None    0.0237    4953.9392   1174773.90
7  20181024        None        None    0.0191   23038.2415   4408682.75
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fund_div`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fund_div.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
