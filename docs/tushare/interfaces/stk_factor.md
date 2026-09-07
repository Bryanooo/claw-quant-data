# `stk_factor` — 股票技术因子（量化因子）

- 分类：股票数据/特色数据
- 功能：获取股票每日技术面因子数据，用于跟踪股票当前走势情况，数据由Tushare社区自产，覆盖全历史
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：5000积分每分钟可以请求100次，8000积分以上每分钟500次，具体请参阅 积分获取办法 注： 1、本接口的前复权行情是从最新一个交易日开始往前复权，是历史当日的数据快照数据不更新 2、pro_bar接口的前复权是动态复权，即以end_date参数开始往前复权，与本接口会存在不一致的可能 3、本接口技术指标都是基于前复权价格计算
- 官方文档：[doc 296](https://tushare.pro/document/2?doc_id=296)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `trade_date` | str | N | 交易日期 （yyyymmdd，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | str | Y | 交易日期 |
| `close` | float | Y | 收盘价 |
| `open` | float | Y | 开盘价 |
| `high` | float | Y | 最高价 |
| `low` | float | Y | 最低价 |
| `pre_close` | float | Y | 昨收价 |
| `change` | float | Y | 涨跌额 |
| `pct_change` | float | Y | 涨跌幅 |
| `vol` | float | Y | 成交量 （手） |
| `amount` | float | Y | 成交额 （千元） |
| `adj_factor` | float | Y | 复权因子 |
| `open_hfq` | float | Y | 开盘价后复权 |
| `open_qfq` | float | Y | 开盘价前复权 |
| `close_hfq` | float | Y | 收盘价后复权 |
| `close_qfq` | float | Y | 收盘价前复权 |
| `high_hfq` | float | Y | 最高价后复权 |
| `high_qfq` | float | Y | 最高价前复权 |
| `low_hfq` | float | Y | 最低价后复权 |
| `low_qfq` | float | Y | 最低价前复权 |
| `pre_close_hfq` | float | Y | 昨收价后复权 |
| `pre_close_qfq` | float | Y | 昨收价前复权 |
| `macd_dif` | float | Y | MACD_DIF (基于前复权价格计算，下同) |
| `macd_dea` | float | Y | MACD_DEA |
| `macd` | float | Y | MACD |
| `kdj_k` | float | Y | KDJ_K |
| `kdj_d` | float | Y | KDJ_D |
| `kdj_j` | float | Y | KDJ_J |
| `rsi_6` | float | Y | RSI_6 |
| `rsi_12` | float | Y | RSI_12 |
| `rsi_24` | float | Y | RSI_24 |
| `boll_upper` | float | Y | BOLL_UPPER |
| `boll_mid` | float | Y | BOLL_MID |
| `boll_lower` | float | Y | BOLL_LOWER |
| `cci` | float | Y | CCI |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stk_factor",
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

df = pro.stk_factor(ts_code='600000.SH', start_date='20220501', end_date='20220520', fields='ts_code,trade_date,macd,kdj_k,kdj_d,kdj_j')
```

## 实际返回示例（官方文档）

```text
注：
1、本接口的前复权行情是从最新一个交易日开始往前复权，是历史当日的数据快照数据不更新
2、pro_bar接口的前复权是动态复权，即以end_date参数开始往前复权，与本接口会存在不一致的可能
3、本接口技术指标都是基于前复权价格计算
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_stk_factor`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/stk_factor.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
