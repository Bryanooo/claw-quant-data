# `top10_cb_holders` — 可转债十大持有人

- 分类：债券专题
- 功能：获取可转债前十大持有人
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：需要5000积分可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 459](https://tushare.pro/document/2?doc_id=459)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码，支持多值输入，如110059.SH,110060.SH |
| `period` | str | N | 报告期（YYYYMMDD格式，年中和年报日期，如20240630,20251231） |
| `start_date` | str | N | 报告期开始日期 |
| `end_date` | str | N | 报告期结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 转债代码 |
| `end_date` | str | Y | 报告期 |
| `holder_rank` | int | Y | 持有排名 |
| `holder_name` | str | Y | 持有人名称 |
| `hold_amount` | float | Y | 持有数量(万张) |
| `hold_ratio` | float | Y | 持有比例(%) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "top10_cb_holders",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "110000.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
# 导入sdk包
import tushare as ts

# 配置凭据，如果已全局配置了，可以忽略。
ts.set_token('<--your-token-->')

# 获取接口实例
pro = ts.pro_api()

# 拉取接口(top10_cb_holders)数据
# <请写入示例参数的具体含义>。示例：获取转债110059.SH，2025年中期报告数据
df = pro.top10_cb_holders(ts_code="110059.SH", period="20250630")
print(df)
```

## 实际返回示例（官方文档）

```text
ts_code  end_date  holder_rank                                 holder_name      hold_amount     hold_ratio
0  110059.SH  20250630            1                              中国移动通信集团广东有限公司     9085.323       23.78
1  110059.SH  20250630            2                                中信建投证券股份有限公司     2449.408        6.41
2  110059.SH  20250630            3      招商银行股份有限公司-博时中证可转债及可交换债券交易型开放式指数证券投资基金     2203.914        5.77
3  110059.SH  20250630            4                    登记结算系统债券回购质押专用账户(中国工商银行)     2014.168        5.27
4  110059.SH  20250630            5              登记结算系统债券回购质押专用账户(中信建投证券股份有限公司)     1488.903        3.90
5  110059.SH  20250630            6                登记结算系统债券回购质押专用账户(招商银行股份有限公司)     1132.656        2.96
6  110059.SH  20250630            7  中信证券股份有限公司-海富通上证投资级可转债及可交换债券交易型开放式指数证券投资基金      631.579        1.65
7  110059.SH  20250630            8                    登记结算系统债券回购质押专用账户(中国农业银行)      586.084        1.53
8  110059.SH  20250630            9                    登记结算系统债券回购质押专用账户(中国建设银行)      560.471        1.47
9  110059.SH  20250630           10                  中国银行股份有限公司-华泰保兴尊合债券型证券投资基金      455.901        1.19
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_top10_cb_holders`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/top10_cb_holders.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
