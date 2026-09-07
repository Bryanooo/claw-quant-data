# `p_get` — 自选股组合查询

- 分类：自选组合
- 功能：查询组合的成分列表
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 449](https://tushare.pro/document/2?doc_id=449)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `name` | str | Y | 组合名称 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `id` | int | Y | 编号 |
| `ts_code` | str | Y | 成分代码 |
| `ts_type` | str | Y | 成份类型（用户自定义类型，比如按行业、按概念板块或其他） |
| `name` | str | Y | 名称 |
| `desc` | str | Y | 描述 |
| `weight` | float | Y | 权重 |
| `create_time` | datetime | Y | 创建时间 |
| `update_time` | datetime | Y | 修改时间 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "p_get",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "name": "测试"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
# 初始化pro接口实例
pro = ts.pro_api()


# 查看我的组合列表
df = pro.p_list()
print(df)

# 查看某个组合的成份列表
df = pro.p_get(name="我的股票池", fields="ts_code,create_time,update_time")
print(df)
```

## 实际返回示例（官方文档）

```text
id   name         desc          create_time          update_time
0  51  我的股票池  默认选取股票10只股票  2026-03-19 10:40:45  2026-03-19 10:45:57
1  41    组合1        测试组合1  2026-03-13 14:31:58  2026-03-13 14:31:58
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_p_get`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/p_get.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
