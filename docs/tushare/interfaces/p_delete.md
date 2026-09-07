# `p_delete` — 自选股组合删除

- 分类：自选组合
- 功能：删除自选股组合
- Token 权限：**有权限**（权限层已通过，接口进入参数校验）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 447](https://tushare.pro/document/2?doc_id=447)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已封装（写接口，不进入采集调度）；代码：[service/tushare_catalog.py:TushareInterfaceCatalog](../../../service/tushare_catalog.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `name` | int | Y | 组合名称 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `status` | bool | Y | 是否执行成功 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "p_delete",
  "token": "${TUSHARE_TOKEN}",
  "params": {},
  "fields": ""
}'
```

## 官方 SDK 示例

```python
# 删除组合(我的股票池)
df=pro.p_delete(name="我的股票池")
```

## 实际返回示例（官方文档）

```text
status
    0   True
```

## claw-quant 存储契约

这是账户写接口，只提供显式调用契约，不进入采集任务和定时调度。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
