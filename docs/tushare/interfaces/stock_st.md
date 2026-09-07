# `stock_st` — ST股票列表

- 分类：股票数据/基础数据
- 功能：获取ST股票列表，可根据交易日期获取历史上每天的ST列表
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：3000积分起 提示：每天上午9:20更新，单次请求最大返回1000行数据，可循环提取,本接口数据从20000101开始,太早历史无法补齐
- 官方文档：[doc 397](https://tushare.pro/document/2?doc_id=397)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/basic/stock_st.py](../../../collectors/stock/basic/stock_st.py)、[collectors/stock/basic/stock_st.py:StockSTCollector](../../../collectors/stock/basic/stock_st.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `trade_date` | str | N | 交易日期（格式：YYYYMMDD下同） |
| `start_date` | str | N | 开始时间 |
| `end_date` | str | N | 结束时间 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `name` | str | Y | 股票名称 |
| `trade_date` | str | Y | 交易日期 |
| `type` | str | Y | 类型 |
| `type_name` | str | Y | 类型名称 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stock_st",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

#获取20250813日所有的ST股票
df = pro.stock_st(trade_date='20250813')
```

## 实际返回示例（官方文档）

```text
ts_code   name trade_date type type_name
0    300313.SZ  *ST天山   20250813   ST     风险警示板
1    605081.SH  *ST太和   20250813   ST     风险警示板
2    300391.SZ  *ST长药   20250813   ST     风险警示板
3    300343.SZ   ST联创   20250813   ST     风险警示板
4    300044.SZ   ST赛为   20250813   ST     风险警示板
..         ...    ...        ...  ...       ...
170  300175.SZ   ST朗源   20250813   ST     风险警示板
171  603721.SH  *ST天择   20250813   ST     风险警示板
172  600289.SH   ST信通   20250813   ST     风险警示板
173  000929.SZ  *ST兰黄   20250813   ST     风险警示板
174  000638.SZ  *ST万方   20250813   ST     风险警示板
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
