# `bond_blk_detail` — 大宗交易明细

- 分类：债券专题
- 功能：获取沪深交易所债券大宗交易数据 注：本接口目前只有深交所的大宗交易明细，上交所明细已经包含在大宗交易接口里，未单独罗列。
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户满5000积分有数据权限，单次最大1000条，可根据日期循环提取，总量不限制
- 官方文档：[doc 272](https://tushare.pro/document/2?doc_id=272)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 债券代码 |
| `trade_date` | str | N | 交易日期（YYYYMMDD格式，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | 债券代码 |
| `name` | str | Y | 债券名称 |
| `price` | float | Y | 成交价（元） |
| `vol` | float | Y | 成交数量（万股/万份/万张/万手） |
| `amount` | float | Y | 成交金额（万元） |
| `buy_dp` | str | Y | 买方营业部 |
| `sell_dp` | str | Y | 卖方营业部 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "bond_blk_detail",
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

df = pro.bond_blk_detail(start_date='20210701', end_date='20210930')
```

## 实际返回示例（官方文档）

```text
trade_date  ts_code    name     price     vol    amount                        buy_dp          sell_dp
0     20210930  149642.SZ  21长城08  100.07   50.00   5003.50                       机构专用             机构专用
1     20210930  149642.SZ  21长城08  100.00   65.00   6500.00                       机构专用             机构专用
2     20210930  149641.SZ  21长城07  100.00  100.00  10000.00                       机构专用             机构专用
3     20210930  149633.SZ  21广发10   99.83   25.00   2495.75                       机构专用             机构专用
4     20210930  149633.SZ  21广发10   99.82   25.00   2495.50                       机构专用             机构专用
..         ...        ...     ...     ...     ...       ...                        ...              ...
995   20210924  138246.SZ  东道02D1  110.17   26.30   2897.47  中国国际金融股份有限公司上海黄浦区湖滨路证券营业部             机构专用
996   20210924  137995.SZ  21即墨A3  101.75   15.00   1526.25      华泰证券股份有限公司临沂金雀山路证券营业部             机构专用
997   20210924  137995.SZ  21即墨A3  101.74   15.00   1526.10                       机构专用             机构专用
998   20210924  137995.SZ  21即墨A3  101.73   15.00   1525.95                       机构专用  华泰证券股份有限公司山东分公司
999   20210924  137942.SZ   美满03次  103.61   30.00   3108.30  中国国际金融股份有限公司上海黄浦区湖滨路证券营业部
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_bond_blk_detail`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/bond_blk_detail.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
