# `pro_bar` — A股复权行情

- 分类：股票数据/行情数据
- 功能：A股复权行情
- Token 权限：**依底层接口权限**（官方文档明确说明 pro_bar 不支持 HTTP 调用）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 146](https://tushare.pro/document/2?doc_id=146)、[doc 109](https://tushare.pro/document/2?doc_id=109)
- HTTP：不支持（SDK 组合接口）
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 证券代码 |
| `start_date` | str | N | 开始日期 (格式：YYYYMMDD) |
| `end_date` | str | N | 结束日期 (格式：YYYYMMDD) |
| `asset` | str | Y | 资产类别：E股票 I沪深指数 FT期货 FD基金 O期权，默认E |
| `adj` | str | N | 复权类型(只针对股票)：None未复权 qfq前复权 hfq后复权 , 默认None |
| `freq` | str | Y | 数据频度 ：1MIN表示1分钟（1/5/15/30/60分钟） D日线 ，默认D |
| `ma` | list | N | 均线，支持任意周期的均价和均量，输入任意合理int数值 |

## 输出契约

当前官方目录没有可提取的输出字段表。

## 官方 SDK 示例

```python
#取000001的前复权行情
df = ts.pro_bar(ts_code='000001.SZ', adj='qfq', start_date='20180101', end_date='20181011')

#取000001的后复权行情
df = ts.pro_bar(ts_code='000001.SZ', adj='hfq', start_date='20180101', end_date='20181011')
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
