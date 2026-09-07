# `factor_value` — 因子值

- 分类：量化因子库
- 功能：获取Tushare因子库里各因子的数值，目前是基于daily的时间序列数值。
- Token 权限：**有权限**（权限层已通过，接口进入参数校验）
- 官方权限要求：因子库为单独权限接口，对个人用户2000元一年，机构用户2万元一年，5000积分以上可试用，请在“ 权限中心 ”勾选 因子库 开通。
- 官方文档：[doc 490](https://tushare.pro/document/2?doc_id=490)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `factor_name` | str | N | 因子名称（基于因子列表的名称） |
| `trade_date` | str | N | 交易日期：YYYYMMDD格式 |
| `start_date` | str | N | 开始日期：YYYYMMDD格式 |
| `end_date` | str | N | 结束日期：YYYYMMDD格式 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `factor_name` | str | Y | 因子名称 |
| `ts_code` | str | Y | 证券代码 |
| `trade_date` | str | Y | 交易日期，格式YYYYMMDD |
| `factor_value` | float | Y | 因子值 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "factor_value",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
# 导入sdk包
import tushare as ts


# 获取接口实例
pro = ts.pro_api()

# 按日期提取某日所有股票的某个因子的全部数据
df = pro.factor_value(trade_date='20260812', factor_name='MACD')

# 按股票提取全部因子某一天的数据
df = pro.factor_value(trade_date='20260812', ts_code='600000.SH')

print(df)
```

## 实际返回示例（官方文档）

```text
factor_name    ts_code trade_date  factor_value
0   bias_std_turn_63d_504d  000566.SZ   20100104     -0.220831
1   bias_std_turn_63d_504d  000623.SZ   20100104     -0.341817
2   bias_std_turn_63d_504d  000731.SZ   20100104     -0.229821
3   bias_std_turn_63d_504d  000525.SZ   20100104     -0.073316
4  bias_std_turn_126d_504d  000767.SZ   20100104      0.115651
5       bias_turn_42d_252d  000713.SZ   20100104      0.026199
6        avg_turnover_252d  000100.SZ   20100104      0.000233
7   bias_std_turn_63d_504d  000571.SZ   20100104      0.291333
8   bias_std_turn_63d_504d  000629.SZ   20100104     -0.789451
9   bias_std_turn_63d_504d  000738.SZ   20100104     -0.228540
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_factor_value`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/factor_value.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

每日全量采集按 `factor_name + trade_date` 扇出，一个请求覆盖该因子当天的全部股票。
禁止按全部股票逐只扇出，因为约 5890 次调用会超过接口 1000 次/日配额。因子宇宙
从 `tushare_norm_factor_value` 的历史观测冻结；新库为空时先运行一条单股票发现任务。
硬日配额触发后，同接口剩余任务整体延迟到下一上海自然日 00:05 再重试。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
