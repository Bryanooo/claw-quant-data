# `stk_account` — 股票账户开户数据

- 分类：股票数据/参考数据
- 功能：获取股票账户开户数据，统计周期为一周
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：600积分可调取，具体请参阅 积分获取办法 注：此数据官方已经停止更新。
- 官方文档：[doc 164](https://tushare.pro/document/2?doc_id=164)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `date` | str | N | 日期 |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `date` | str | Y | 统计周期 |
| `weekly_new` | float | Y | 本周新增（万） |
| `total` | float | Y | 期末总账户数（万） |
| `weekly_hold` | float | Y | 本周持仓账户数（万） |
| `weekly_trade` | float | Y | 本周参与交易账户数（万） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stk_account",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "start_date": "20260730",
    "end_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.stk_account(start_date='20180101', end_date='20181231')
```

## 实际返回示例（官方文档）

```text
date      weekly_new     total weekly_hold weekly_trade
0   20181228       20.81  14650.44        None         None
1   20181221       21.04  14629.63        None         None
2   20181214       21.21  14608.59        None         None
3   20181207       22.28  14587.38        None         None
4   20181130       23.56  14565.10        None         None
5   20181123       24.16  14541.54        None         None
6   20181116       24.57  14517.38        None         None
7   20181109       24.11  14492.81        None         None
8   20181102       23.97  14468.70        None         None
9   20181026       26.00  14444.73        None         None
10  20181019       24.13  14418.73        None         None
11  20181012       25.30  14394.60        None         None
12  20180928       20.09  14369.30        None         None
13  20180921       23.24  14349.21        None         None
14  20180914       24.08  14325.97        None         None
15  20180907       23.58  14301.89        None         None
16  20180831       24.06  14278.31        None         None
17  20180824       23.12  14254.25        None         None
18  20180817       23.04  14231.12        None         None
19  20180810       23.96  14208.09        None         None
20  20180803       24.22  14184.12        None         None
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_stk_account`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/stk_account.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
