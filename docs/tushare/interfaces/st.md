# `st` — ST风险警示板股票

- 分类：股票数据/基础数据
- 功能：ST风险警示板股票列表
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：6000积分可提取数据，具体请参阅 积分获取办法
- 官方文档：[doc 423](https://tushare.pro/document/2?doc_id=423)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/basic/stock_st.py](../../../collectors/stock/basic/stock_st.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `pub_date` | str | N | 发布日期 |
| `imp_date` | str | N | 实施日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `name` | str | Y | 股票名称 |
| `pub_date` | str | Y | 发布日期 |
| `imp_date` | str | Y | 实施日期 |
| `st_type` | str | Y | 类型 |
| `st_reason` | str | Y | st变更原因 |
| `st_explain` | str | Y | st变更详细原因 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "st",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SZ"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
# 拉取接口st数据
    df = pro.st(**{
    "ts_code": "300125.SZ",
    "pub_date": "",
    "imp_date": ""
}, fields=[
    "ts_code",
    "name",
    "pub_date",
    "imp_date",
    "st_type",
    "st_reason",
    "st_explain"
])
    print(df)
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
