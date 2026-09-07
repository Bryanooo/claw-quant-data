# `ths_member` — 概念板块成分

- 分类：股票数据/打板专题数据
- 功能：获取概念板块成分列表
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 261](https://tushare.pro/document/2?doc_id=261)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/index/ths_member.py:ThsMemberCollector](../../../collectors/index/ths_member.py)、[collectors/stock/board/ths_member.py:ThsMemberCollector](../../../collectors/stock/board/ths_member.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 板块指数代码 |
| `con_code` | str | N | 股票代码 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 指数代码 |
| `con_code` | str | Y | 股票代码 |
| `con_name` | str | Y | 股票名称 |
| `weight` | float | N | 权重(暂无) |
| `in_date` | str | N | 纳入日期(暂无) |
| `out_date` | str | N | 剔除日期(暂无) |
| `is_new` | str | N | 是否最新Y是N否 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "ths_member",
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

df = pro.ths_member(ts_code='885800.TI')
```

## 实际返回示例（官方文档）

```text
ts_code         con_code     con_name
0   885800.TI  000016.SZ  深康佳A
1   885800.TI  000049.SZ  德赛电池
2   885800.TI  002008.SZ  大族激光
3   885800.TI  002036.SZ  联创电子
4   885800.TI  002055.SZ  得润电子
..        ...        ...   ...
87  885800.TI  688127.SH  蓝特光学
88  885800.TI  688157.SH  松井股份
89  885800.TI  688286.SH  敏芯股份
90  885800.TI  688312.SH  燕麦科技
91  885800.TI  688386.SH  泛亚微透

[92 rows x 3 columns]
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
