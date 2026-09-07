# `factor_list` — 因子列表

- 分类：量化因子库
- 功能：提取 Tushare自主研发 生产的因子列表，包括因子名、因子分类和计算逻辑等信息
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：因子库为单独权限接口，对个人用户2000元一年，机构用户2万元一年，请在“ 权限中心 ”勾选 因子库 开通。
- 官方文档：[doc 486](https://tushare.pro/document/2?doc_id=486)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `factor_name` | str | N | 因子名称 |
| `asset_type` | str | N | 资产类别：STK股票，IDX指数，ETF，CB可转债 【当前只提供STK股票】 |
| `factor_type` | str | N | 因子类别，详见下方明细 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `factor_name` | str | Y | 因子名称 |
| `asset_type` | str | Y | 证券类型：STK股票，IDX指数，ETF，CB可转债 【当前只提供STK股票】 |
| `factor_type` | str | Y | 因子分类 |
| `factor_desc` | str | Y | 因子描述及算法逻辑 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "factor_list",
  "token": "${TUSHARE_TOKEN}",
  "params": {},
  "fields": ""
}'
```

## 官方 SDK 示例

```python
# 导入sdk包
import tushare as ts

# 获取接口实例
pro = ts.pro_api()

# 拉取全部因子列表数据
df = pro.factor_list()
print(df)

#按因子类型提取并指定字段输出
df = pro.factor_list(factor_type='Risk', fields='factor_name,factor_type,factor_desc')
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
