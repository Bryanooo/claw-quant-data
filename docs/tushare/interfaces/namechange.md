# `namechange` — 股票曾用名

- 分类：股票数据/基础数据
- 功能：历史名称变更记录
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 100](https://tushare.pro/document/2?doc_id=100)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/basic/stock_namechange.py:NameChangeCollector](../../../collectors/stock/basic/stock_namechange.py)、[service/tools/stock/namechange.py](../../../service/tools/stock/namechange.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS代码 |
| `start_date` | str | N | 公告开始日期 |
| `end_date` | str | N | 公告结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `name` | str | Y | 证券名称 |
| `start_date` | str | Y | 开始日期 |
| `end_date` | str | Y | 结束日期 |
| `ann_date` | str | Y | 公告日期 |
| `change_reason` | str | Y | 变更原因 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "namechange",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SZ"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.namechange(ts_code='600848.SH', fields='ts_code,name,start_date,end_date,change_reason')
```

## 实际返回示例（官方文档）

```text
ts_code    name    start_date   end_date      change_reason
0  600848.SH   上海临港   20151118      None         改名
1  600848.SH   自仪股份   20070514  20151117         撤销ST
2  600848.SH   ST自仪     20061026  20070513         完成股改
3  600848.SH   SST自仪   20061009  20061025        未股改加S
4  600848.SH   ST自仪     20010508  20061008         ST
5  600848.SH   自仪股份  19940324  20010507         其他
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
