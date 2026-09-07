# `cb_call` — 可转债赎回信息

- 分类：债券专题
- 功能：获取可转债到期赎回、强制赎回等信息。数据来源于公开披露渠道，供个人和机构研究使用，请不要用于数据商业目的。
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 269](https://tushare.pro/document/2?doc_id=269)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 转债代码，支持多值输入 |
| `ann_date` | str | N | 公告日期(YYYYMMDD格式，下同) |
| `start_date` | str | N | 公告开始日期 |
| `end_date` | str | N | 公告结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 转债代码 |
| `call_type` | str | Y | 赎回类型：到赎、强赎 |
| `is_call` | str | Y | 是否赎回：已满足强赎条件、公告提示强赎、公告实施强赎、公告到期赎回、公告不强赎 |
| `ann_date` | str | Y | 公告/提示日期 |
| `call_date` | str | Y | 赎回日期 |
| `call_price` | float | Y | 赎回价格(含税，元/张) |
| `call_price_tax` | float | Y | 赎回价格(扣税，元/张) |
| `call_vol` | float | Y | 赎回债券数量(张) |
| `call_amount` | float | Y | 赎回金额(万元) |
| `payment_date` | str | Y | 行权后款项到账日 |
| `call_reg_date` | str | Y | 赎回登记日 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "cb_call",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "110000.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api('your token')

#获取可转债行情
df = pro.cb_call(fields='ts_code,call_type,is_call,ann_date,call_date,call_price')
```

## 实际返回示例（官方文档）

```text
ts_code call_type is_call  ann_date call_date call_price
0    123069.SZ        强赎   公告不强赎  20210821      None       None
1    113621.SH        强赎   公告不强赎  20210821      None       None
2    113528.SH        强赎   公告不强赎  20210821      None       None
3    113012.SH        强赎    公告强赎  20210818  20210903   100.6700
4    128113.SZ        强赎   公告不强赎  20210818      None       None
..         ...       ...     ...       ...       ...        ...
466  125069.SZ        强赎    公告强赎  20050429  20050422   101.8000
467  125630.SZ        强赎   公告不强赎  20040624      None       None
468  100009.SH        强赎    公告强赎  20040511  20040423   100.1300
469  125002.SZ        强赎    公告强赎  20040430  20040423   101.5000
470  125629.SZ        强赎    公告强赎  20040414  20040406   105.0000
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_cb_call`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/cb_call.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
