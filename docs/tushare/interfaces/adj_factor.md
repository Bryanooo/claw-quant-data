# `adj_factor` — 复权因子

- 分类：股票数据/行情数据
- 功能：本接口由Tushare自行生产，获取股票复权因子，可提取单只股票全部历史复权因子，也可以提取单日全部股票的复权因子。
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：2000积分起，5000以上可高频调取
- 官方文档：[doc 28](https://tushare.pro/document/2?doc_id=28)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `trade_date` | str | N | 交易日期(YYYYMMDD，下同) |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | str | Y | 交易日期 |
| `adj_factor` | float | Y | 复权因子 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "adj_factor",
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

#提取000001全部复权因子
df = pro.adj_factor(ts_code='000001.SZ', trade_date='')


#提取2018年7月18日复权因子
df = pro.adj_factor(ts_code='', trade_date='20180718')
```

## 实际返回示例（官方文档）

```text
ts_code trade_date  adj_factor
0     000001.SZ   20180809     108.031
1     000001.SZ   20180808     108.031
2     000001.SZ   20180807     108.031
3     000001.SZ   20180806     108.031
4     000001.SZ   20180803     108.031
5     000001.SZ   20180802     108.031
6     000001.SZ   20180801     108.031
7     000001.SZ   20180731     108.031
8     000001.SZ   20180730     108.031
9     000001.SZ   20180727     108.031
10    000001.SZ   20180726     108.031
11    000001.SZ   20180725     108.031
12    000001.SZ   20180724     108.031
13    000001.SZ   20180723     108.031
14    000001.SZ   20180720     108.031
15    000001.SZ   20180719     108.031
16    000001.SZ   20180718     108.031
17    000001.SZ   20180717     108.031
18    000001.SZ   20180716     108.031
19    000001.SZ   20180713     108.031
20    000001.SZ   20180712     108.031
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_adj_factor`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/adj_factor.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
