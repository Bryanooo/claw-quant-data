# `p_save` — 自选股组合保存

- 分类：自选组合
- 功能：创建或修改自选股组合
- Token 权限：**有权限**（权限层已通过，接口进入参数校验）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 445](https://tushare.pro/document/2?doc_id=445)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已封装（写接口，不进入采集调度）；代码：[service/tushare_catalog.py:TushareInterfaceCatalog](../../../service/tushare_catalog.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `name` | str | Y | 组合名称 |
| `desc` | str | N | 描述 |
| `items` | list | Y | 成份列表; 每个元素包含 ts_code:str ts_type:str weight:float name:str desc:str |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `id` | int | Y | 主键 |
| `ts_code` | str | Y | 成分代码 |
| `ts_type` | str | Y | 成份类型 |
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
  "api_name": "p_save",
  "token": "${TUSHARE_TOKEN}",
  "params": {},
  "fields": ""
}'
```

## 官方 SDK 示例

```python
import tushare as ts

pro = ts.pro_api()

# 选取股票列表
df = pro.stock_basic()
df_stock = df.head(10)
print(df_stock)

# 保存到自定义组合
p_items = df_stock[["ts_code", "name"]]
df_p1 = pro.p_save(name="我的股票池", items=p_items.to_dict(orient='records'))
print(df_p1)
```

## 实际返回示例（官方文档）

```text
id    ts_code   name  desc  weight          create_time          update_time
0  44  000001.SZ   平安银行  None     0.0  2026-03-19 10:40:45  2026-03-19 10:40:45
1  45  000002.SZ    万科Ａ  None     0.0  2026-03-19 10:40:45  2026-03-19 10:40:45
2  46  000004.SZ  *ST国华  None     0.0  2026-03-19 10:40:45  2026-03-19 10:40:45
3  47  000006.SZ   深振业Ａ  None     0.0  2026-03-19 10:40:45  2026-03-19 10:40:45
4  48  000007.SZ    全新好  None     0.0  2026-03-19 10:40:45  2026-03-19 10:40:45
5  49  000008.SZ   神州高铁  None     0.0  2026-03-19 10:40:45  2026-03-19 10:40:45
6  50  000009.SZ   中国宝安  None     0.0  2026-03-19 10:40:45  2026-03-19 10:40:45
7  51  000010.SZ   美丽生态  None     0.0  2026-03-19 10:40:45  2026-03-19 10:40:45
8  52  000011.SZ   深物业A  None     0.0  2026-03-19 10:40:45  2026-03-19 10:40:45
9  53  000012.SZ    南玻Ａ  None     0.0  2026-03-19 10:40:45  2026-03-19 10:40:45
```

## claw-quant 存储契约

这是账户写接口，只提供显式调用契约，不进入采集任务和定时调度。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
