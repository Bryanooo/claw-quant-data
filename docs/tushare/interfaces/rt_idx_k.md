# `rt_idx_k` — 交易所指数实时日线

- 分类：指数专题
- 功能：获取交易所指数实时日线行情，支持按代码或代码通配符一次性提取全部交易所指数实时日k线行情
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：本接口是单独开权限的数据，单独申请权限请参考 权限列表
- 官方文档：[doc 403](https://tushare.pro/document/2?doc_id=403)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 指数代码，支持通配符方式，e.g. 0*.SH、3*.SZ、000001.SH |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 指数代码 |
| `name` | str | Y | 指数名称 |
| `trade_time` | str | Y | 交易时间 |
| `close` | float | Y | 现价 |
| `pre_close` | float | Y | 昨收 |
| `high` | float | Y | 最高价 |
| `open` | float | Y | 开盘价 |
| `low` | float | Y | 最低价 |
| `vol` | float | Y | 成交量 |
| `amount` | float | Y | 成交金额（元） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "rt_idx_k",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取单个指数实时行情
df = pro.rt_idx_k(ts_code='000001.SH')

#获取多个指数实时行情,以上证综指和深证A指为例
df = pro.rt_idx_k(ts_code='000001.SH,399107.SZ')

#获取上交所所有指数实时行情，同时指定输出字段
df = pro.rt_idx_k(ts_code='0*.SH', fields='ts_code,name,close,vol')
```

## 实际返回示例（官方文档）

```text
ts_code    name       close           vol
0    000851.SH  百发100   19517.5514  2.035695e+07
1    000934.SH    中证金融   6203.0781  6.711314e+07
2    000010.SH  上证180    9773.2466  1.135439e+08
3    000065.SH    上证龙头   3527.1942  5.541939e+07
4    000033.SH    上证材料   3232.1719  2.889464e+07
..         ...     ...         ...           ...
195  000888.SH    上证收益   4420.1632  4.787276e+08
196  000011.SH    基金指数   7103.0192  1.107185e+09
197  000008.SH    综合指数   3668.1847  1.011677e+08
198  000075.SH    医药等权   7170.0801  4.000854e+06
199  000029.SH  180价值    4396.8748  5.572026e+07
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
