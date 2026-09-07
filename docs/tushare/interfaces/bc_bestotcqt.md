# `bc_bestotcqt` — 柜台流通式债券最优报价

- 分类：债券专题
- 功能：柜台流通式债券最优报价
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少500积分可以试用调取，2000积分以上频次相对较高，积分越多权限越大，具体请参阅 积分获取办法
- 官方文档：[doc 323](https://tushare.pro/document/2?doc_id=323)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 报价日期(YYYYMMDD格式，下同) |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `ts_code` | str | N | TS代码 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 报价日期 |
| `ts_code` | str | N | 债券编码 |
| `name` | str | N | 债券简称 |
| `remain_maturity` | str | N | 剩余期限 |
| `bond_type` | str | N | 债券类型 |
| `best_buy_bank` | str | N | 最优报买价方 |
| `best_buy_yield` | float | N | 投资者最优买入价到期收益率（%） |
| `best_buy_price` | float | Y | 投资者最优买入全价 |
| `best_sell_bank` | str | N | 最优卖报价方 |
| `best_sell_yield` | float | N | 投资者最优卖出价到期收益率（%） |
| `best_sell_price` | float | Y | 投资者最优卖出全价 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "bc_bestotcqt",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api(your token)
#获取柜台流通式债券最优报价
df = pro.bc_bestotcqt(ts_code='200013.BC',start_date='20240325',end_date='20240329',fields='trade_date,ts_code,name,remain_maturity,best_buy_bank,best_buy_yield,best_sell_bank,best_sell_yield')
```

## 实际返回示例（官方文档）

```text
trade_date ts_code name remain_maturity best_buy_bank best_buy_yield best_sell_bank best_sell_yield
0   20240325  200013.BC  20附息国债13     1年211天       建设银行         1.9041        工商银行          1.9227
1   20240326  200013.BC  20附息国债13     1年210天       工商银行         1.8813        工商银行          1.9133
2   20240327  200013.BC  20附息国债13     1年209天       工商银行         1.8718        工商银行          1.9039
3   20240328  200013.BC  20附息国债13     1年208天       工商银行         1.8623        建设银行          1.8921
4   20240329  200013.BC  20附息国债13     1年207天       工商银行         1.8528        交通银行          1.8464
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_bc_bestotcqt`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/bc_bestotcqt.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
