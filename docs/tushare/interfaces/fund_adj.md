# `fund_adj` — 基金复权因子

- 分类：ETF专题
- 功能：获取基金复权因子，用于计算基金复权行情
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积2000积分可调取，超过5000积分以上频次相对较高。具体请参阅 积分获取办法
- 官方文档：[doc 199](https://tushare.pro/document/2?doc_id=199)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS基金代码（支持多只基金输入） |
| `trade_date` | str | N | 交易日期（格式：yyyymmdd，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `offset` | str | N | 开始行数 |
| `limit` | str | N | 最大行数 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | ts基金代码 |
| `trade_date` | str | Y | 交易日期 |
| `adj_factor` | float | Y | 复权因子 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fund_adj",
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

df = pro.fund_adj(ts_code='513100.SH', start_date='20190101', end_date='20190926')
```

## 实际返回示例（官方文档）

```text
ts_code    trade_date  adj_factor
0    513100.SH   20190926         1.0
1    513100.SH   20190925         1.0
2    513100.SH   20190924         1.0
3    513100.SH   20190923         1.0
4    513100.SH   20190920         1.0
5    513100.SH   20190919         1.0
6    513100.SH   20190918         1.0
7    513100.SH   20190917         1.0
8    513100.SH   20190916         1.0
9    513100.SH   20190912         1.0
10   513100.SH   20190911         1.0
11   513100.SH   20190910         1.0
12   513100.SH   20190909         1.0
13   513100.SH   20190906         1.0
14   513100.SH   20190905         1.0
15   513100.SH   20190904         1.0
16   513100.SH   20190903         1.0
17   513100.SH   20190902         1.0
18   513100.SH   20190830         1.0
19   513100.SH   20190829         1.0
20   513100.SH   20190828         1.0
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fund_adj`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fund_adj.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
