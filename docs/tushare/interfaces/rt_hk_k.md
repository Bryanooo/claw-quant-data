# `rt_hk_k` — 港股实时日线

- 分类：港股数据
- 功能：获取港股实时日k线行情，支持按股票代码及股票代码通配符一次性提取全部股票实时日k线行情
- Token 权限：**有权限**（2026-09-09 双重实时探测均返回成功）
- 官方权限要求：本接口是单独开权限的数据，单独申请权限请参考 权限列表
- 官方文档：[doc 383](https://tushare.pro/document/2?doc_id=383)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[`collectors/tushare_raw.py:CatalogRawCollector`](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 支持通配符方式，e.g. 00001.HK、02*.HK |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `pre_close` | float | Y | 昨收价 |
| `close` | float | Y | 收盘价 |
| `high` | float | Y | 最高价 |
| `open` | float | Y | 开盘价 |
| `low` | float | Y | 最低价 |
| `vol` | float | Y | 成交量（股） |
| `amount` | float | Y | 成交额(元) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "rt_hk_k",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "00001.HK"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取特定股票实时日线
df = pro.rt_hk_k(ts_code='00001.HK')

#获取今日开盘以来部分港股实时日线
df = pro.rt_hk_k(ts_code='01*.HK')
```

## 实际返回示例（官方文档）

```text
ts_code  pre_close  close   high   open    low            vol       amount
0    01508.HK      1.040  1.030  1.050  1.040  1.030  14971000.0  15564320.00
1    01314.HK      0.210  0.211  0.211  0.210  0.210     40000.0      8420.00
2    01848.HK      3.940  3.910  3.950  3.940  3.890    300500.0   1176380.00
3    01150.HK      0.091  0.103  0.106  0.106  0.100     45000.0      4580.00
4    01875.HK      1.860  1.970  1.970  1.930  1.890    164000.0    316064.00
..        ...        ...    ...    ...    ...    ...         ...          ...
746  01653.HK      0.260  0.000  0.000  0.000  0.000         0.0         0.00
747  01729.HK      5.440  5.790  5.800  5.440  5.380   6778621.0  37845706.87
748  01608.HK      0.290  0.285  0.290  0.290  0.285    142000.0     41170.00
749  01247.HK      1.700  1.700  1.750  1.740  1.700    120400.0    206708.00
750  01878.HK      1.890  1.900  1.950  1.900  1.840    191100.0    362691.00
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_rt_hk_k`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/rt_hk_k.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
