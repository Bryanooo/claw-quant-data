# `hk_tradecal` — 港股交易日历

- 分类：港股数据
- 功能：获取交易日历
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积累2000积分才可调取
- 官方文档：[doc 250](https://tushare.pro/document/2?doc_id=250)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `is_open` | str | N | 是否交易 '0'休市 '1'交易 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `cal_date` | str | Y | 日历日期 |
| `is_open` | int | Y | 是否交易 '0'休市 '1'交易 |
| `pretrade_date` | str | Y | 上一个交易日 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "hk_tradecal",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "start_date": "20260730",
    "end_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.hk_tradecal(start_date='20200101', end_date='20200708')
```

## 实际返回示例（官方文档）

```text
cal_date     is_open pretrade_date
    0  20200708        1      20200707
    1  20200707        1      20200706
    2  20200706        1      20200703
    3  20200705        0      20200702
    4  20200704        0      20200702
    5  20200703        1      20200702
    6  20200702        1      20200630
    7  20200701        0      20200629
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_hk_tradecal`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/hk_tradecal.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
