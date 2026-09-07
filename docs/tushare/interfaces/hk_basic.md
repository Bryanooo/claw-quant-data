# `hk_basic` — 港股列表

- 分类：港股数据
- 功能：获取港股列表信息 数量：单次可提取全部在交易的港股列表数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 191](https://tushare.pro/document/2?doc_id=191)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS代码 |
| `list_status` | str | N | 上市状态 L上市 D退市 P暂停上市 ，默认L |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `name` | str | Y | 股票简称 |
| `fullname` | str | Y | 公司全称 |
| `enname` | str | Y | 英文名称 |
| `cn_spell` | str | Y | 拼音 |
| `market` | str | Y | 市场类别 |
| `list_status` | str | Y | 上市状态 |
| `list_date` | str | Y | 上市日期 |
| `delist_date` | str | Y | 退市日期 |
| `trade_unit` | float | Y | 交易单位 |
| `isin` | str | Y | ISIN代码 |
| `curr_type` | str | Y | 货币代码 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "hk_basic",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "00001.HK"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

#获取全部可交易股票基础信息
df = pro.hk_basic()

#获取全部退市股票基础信息
df = pro.hk_basic(list_status='D')
```

## 实际返回示例（官方文档）

```text
ts_code             name  ...          isin curr_type
0     00001.HK               长和  ...  KYG217651051       HKD
1     00002.HK             中电控股  ...  HK0002007356       HKD
2     00003.HK           香港中华煤气  ...  HK0003000038       HKD
3     00004.HK            九龙仓集团  ...  HK0004000045       HKD
4     00005.HK             汇丰控股  ...  GB0005405286       HKD
5     00006.HK             电能实业  ...  HK0006000050       HKD
6     00007.HK           香港金融集团  ...  BMG4613K1099       HKD
7     00008.HK             电讯盈科  ...  HK0008011667       HKD
8     00009.HK             九号运通  ...  BMG6547Y1057       HKD
9     00010.HK             恒隆集团  ...  HK0010000088       HKD
10    00011.HK             恒生银行  ...  HK0011000095       HKD
11    00012.HK             恒基地产  ...  HK0012000102       HKD
12    00014.HK             希慎兴业  ...  HK0014000126       HKD
13    00015.HK             盈信控股  ...  BMG932121434       HKD
14    00016.HK            新鸿基地产  ...  HK0016000132       HKD
15    00017.HK            新世界发展  ...  HK0017000149       HKD
16    00018.HK           东方报业集团  ...  HK0018000155       HKD
17    00019.HK          太古股份公司A  ...  HK0019000162       HKD
18    00020.HK              会德丰  ...  HK0020000177       HKD
19    00021.HK          大中华地产控股  ...  HK0000132420       HKD
20    00022.HK             茂盛控股  ...  BMG6051D1175       HKD
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_hk_basic`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/hk_basic.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
