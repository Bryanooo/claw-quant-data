# `hm_list` — 游资名录

- 分类：股票数据/打板专题数据
- 功能：获取游资分类名录信息
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：5000积分可以调取，积分获取办法请参阅 积分获取办法
- 官方文档：[doc 311](https://tushare.pro/document/2?doc_id=311)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/board/hm_list.py:HmListCollector](../../../collectors/stock/board/hm_list.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `name` | str | N | 游资名称 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `name` | str | Y | 游资名称 |
| `desc` | str | Y | 说明 |
| `orgs` | None | Y | 关联机构 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "hm_list",
  "token": "${TUSHARE_TOKEN}",
  "params": {},
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#代码示例
pro = ts.pro_api()

df = pro.hm_list()
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
