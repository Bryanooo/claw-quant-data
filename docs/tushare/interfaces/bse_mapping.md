# `bse_mapping` — 北交所新旧代码对照表

- 分类：股票数据/基础数据
- 功能：获取北交所股票代码变更后新旧代码映射表数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：2000积分即可调取
- 官方文档：[doc 375](https://tushare.pro/document/2?doc_id=375)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/basic/bse_mapping.py:BseMappingCollector](../../../collectors/stock/basic/bse_mapping.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `o_code` | str | N | 旧代码 |
| `n_code` | str | N | 新代码 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `name` | str | Y | 股票名称 |
| `o_code` | str | Y | 原代码 |
| `n_code` | str | Y | 新代码 |
| `list_date` | str | Y | 上市日期 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "bse_mapping",
  "token": "${TUSHARE_TOKEN}",
  "params": {},
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取方大新材新旧代码对照数据
df = pro.bse_mapping(o_code='838163.BJ')


#获取全部变更的股票代码对照表
df = pro.bse_mapping()
```

## 实际返回示例（官方文档）

```text
name     o_code   n_code    list_date
0  方大新材  838163.BJ  920163.BJ  20200727
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
