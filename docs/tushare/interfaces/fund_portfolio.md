# `fund_portfolio` — 公募基金持仓数据

- 分类：公募基金
- 功能：获取公募基金持仓数据，季度更新
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：5000积分以上每分钟请求200次，8000积分以上每分钟请求500次，具体请参阅 积分获取办法
- 官方文档：[doc 121](https://tushare.pro/document/2?doc_id=121)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 基金代码 (ts_code,ann_date,period至少输入一个参数) |
| `symbol` | str | N | 股票代码 |
| `ann_date` | str | N | 公告日期（YYYYMMDD格式） |
| `period` | str | N | 季度（每个季度最后一天的日期，比如20131231表示2013年年报） |
| `start_date` | str | N | 报告期开始日期（YYYYMMDD格式） |
| `end_date` | str | N | 报告期结束日期（YYYYMMDD格式） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS基金代码 |
| `ann_date` | str | Y | 公告日期 |
| `end_date` | str | Y | 截止日期 |
| `symbol` | str | Y | 股票代码 |
| `mkv` | float | Y | 持有股票市值(元) |
| `amount` | float | Y | 持有股票数量（股） |
| `stk_mkv_ratio` | float | Y | 占股票市值比 |
| `stk_float_ratio` | float | Y | 占流通股本比例 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fund_portfolio",
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

df = pro.fund_portfolio(ts_code='001753.OF')
```

## 实际返回示例（官方文档）

```text
ts_code  ann_date  end_date     symbol          mkv    amount  \
0    001753.OF  20180823  20180630  603019.SH   3130994.46   68258.0
1    001753.OF  20180718  20180630  600845.SH   3594140.00  136400.0
2    001753.OF  20180718  20180630  600596.SH   5428107.30  335690.0
3    001753.OF  20180718  20180630  600588.SH   3811672.65  155515.0
4    001753.OF  20180718  20180630  600271.SH   3770284.00  149200.0
5    001753.OF  20180823  20180630  300616.SZ     10900.00     100.0
6    001753.OF  20180718  20180630  300577.SZ   4544793.54  110257.0
7    001753.OF  20180718  20180630  300476.SZ   3783780.00  245700.0
8    001753.OF  20180823  20180630  300409.SZ   2895942.00   72200.0
9    001753.OF  20180718  20180630  300208.SZ   5768280.00  588000.0
10   001753.OF  20180823  20180630  300188.SZ   2535922.50  138575.0

     stk_mkv_ratio  stk_float_ratio
0             4.37             0.01
1             5.02             0.02
2             7.57             0.05
3             5.32             0.01
4             5.26             0.01
5             0.02             0.00
6             6.34             0.17
7             5.28             0.07
8             4.04             0.05
9             8.05             0.10
10            3.54             0.03
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fund_portfolio`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fund_portfolio.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
