# `cb_basic` — 可转债基本信息

- 分类：债券专题
- 功能：获取可转债基本信息
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，但有流量控制，5000积分以上频次相对较高，积分越多权限越大，具体请参阅 积分获取办法
- 官方文档：[doc 185](https://tushare.pro/document/2?doc_id=185)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 转债代码 |
| `list_date` | str | N | 上市日期 |
| `exchange` | str | N | 上市交易所 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 转债代码 |
| `bond_full_name` | str | Y | 转债名称 |
| `bond_short_name` | str | Y | 转债简称 |
| `cb_code` | str | Y | 转股申报代码 |
| `cb_type` | str | Y | 转债类型: CB-可转债,EB-可交换债 |
| `stk_code` | str | Y | 正股代码 |
| `stk_short_name` | str | Y | 正股简称 |
| `maturity` | float | Y | 发行期限（年） |
| `par` | float | Y | 面值 |
| `issue_price` | float | Y | 发行价格 |
| `issue_size` | float | Y | 发行总额（元） |
| `remain_size` | float | Y | 债券余额（元） |
| `value_date` | str | Y | 起息日期 |
| `maturity_date` | str | Y | 到期日期 |
| `rate_type` | str | Y | 利率类型 |
| `coupon_rate` | float | Y | 票面利率（%） |
| `add_rate` | float | Y | 补偿利率（%） |
| `pay_per_year` | int | Y | 年付息次数 |
| `list_date` | str | Y | 上市日期 |
| `delist_date` | str | Y | 摘牌日 |
| `exchange` | str | Y | 上市交易所 |
| `conv_start_date` | str | Y | 转股起始日 |
| `conv_end_date` | str | Y | 转股截止日 |
| `conv_stop_date` | str | Y | 停止转股日(提前到期) |
| `first_conv_price` | float | Y | 初始转股价 |
| `conv_price` | float | Y | 最新转股价 |
| `rate_clause` | str | Y | 利率说明 |
| `put_clause` | str | N | 回售条款 |
| `maturity_call_price` | float | N | 到期赎回价格(含税) |
| `maturity_put_price` | float | N | 到期赎回价格(含税)[更名停用，请使用maturity_call_price] |
| `call_clause` | str | N | 赎回条款 |
| `reset_clause` | str | N | 特别向下修正条款 |
| `conv_clause` | str | N | 转股条款 |
| `guarantor` | str | N | 担保人 |
| `guarantee_type` | str | N | 担保方式 |
| `issue_rating` | str | N | 发行信用等级 |
| `newest_rating` | str | N | 最新信用等级 |
| `rating_comp` | str | N | 最新评级机构 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "cb_basic",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "110000.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api(your token)
#获取可转债基础信息列表
df = pro.cb_basic(fields="ts_code,bond_short_name,stk_code,stk_short_name,list_date,delist_date")
```

## 实际返回示例（官方文档）

```text
ts_code bond_short_name   stk_code stk_short_name   list_date delist_date
0    125002.SZ            万科转债  000002.SZ            万科Ａ  2002-06-28  2004-04-30
1    125009.SZ            宝安转券  000009.SZ           中国宝安  1993-02-10  1996-01-01
2    125069.SZ            侨城转债  000069.SZ           华侨城Ａ  2004-01-16  2005-04-29
3    125301.SZ            丝绸转债  000301.SZ           东方盛虹  1998-09-15  2003-08-28
4    126301.SZ            丝绸转2  000301.SZ           东方盛虹  2002-09-24  2006-09-18
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_cb_basic`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/cb_basic.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
