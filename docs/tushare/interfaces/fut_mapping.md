# `fut_mapping` — 期货主力与连续合约

- 分类：期货数据
- 功能：获取期货主力（或连续）合约与月合约映射数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，未来可能调整积分，请尽可能多积累积分。具体请参阅 积分获取办法
- 官方文档：[doc 189](https://tushare.pro/document/2?doc_id=189)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 合约代码 |
| `trade_date` | str | N | 交易日期(YYYYMMDD格式，下同) |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 连续合约代码 |
| `trade_date` | str | Y | 起始日期 |
| `mapping_ts_code` | str | Y | 期货合约代码 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fut_mapping",
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

#获取主力合约TF.CFX每日对应的月合约
df = pro.fut_mapping(ts_code='TF.CFX')
```

## 实际返回示例（官方文档）

```text
ts_code trade_date mapping_ts_code
0     TF.CFX   20190823      TF1912.CFX
1     TF.CFX   20190822      TF1912.CFX
2     TF.CFX   20190821      TF1912.CFX
3     TF.CFX   20190820      TF1912.CFX
4     TF.CFX   20190819      TF1912.CFX
5     TF.CFX   20190816      TF1912.CFX
6     TF.CFX   20190815      TF1912.CFX
7     TF.CFX   20190814      TF1912.CFX
8     TF.CFX   20190813      TF1912.CFX
9     TF.CFX   20190812      TF1909.CFX
10    TF.CFX   20190809      TF1909.CFX
11    TF.CFX   20190808      TF1909.CFX
12    TF.CFX   20190807      TF1909.CFX
13    TF.CFX   20190806      TF1909.CFX
14    TF.CFX   20190805      TF1909.CFX
15    TF.CFX   20190802      TF1909.CFX
16    TF.CFX   20190801      TF1909.CFX
17    TF.CFX   20190731      TF1909.CFX
18    TF.CFX   20190730      TF1909.CFX
19    TF.CFX   20190729      TF1909.CFX
20    TF.CFX   20190726      TF1909.CFX
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fut_mapping`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fut_mapping.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
