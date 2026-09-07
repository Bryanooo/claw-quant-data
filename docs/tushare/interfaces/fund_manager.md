# `fund_manager` — 基金经理

- 分类：公募基金
- 功能：获取公募基金经理数据，包括基金经理简历等数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户有500积分可获取数据，2000积分以上可以提高访问频次
- 官方文档：[doc 208](https://tushare.pro/document/2?doc_id=208)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 基金代码，支持多只基金，逗号分隔 |
| `ann_date` | str | N | 公告日期，格式：YYYYMMDD |
| `name` | str | N | 基金经理姓名 |
| `offset` | intint | N | 开始行数 |
| `limit` | int | N | 每页行数 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 基金代码 |
| `ann_date` | str | Y | 公告日期 |
| `name` | str | Y | 基金经理姓名 |
| `gender` | str | Y | 性别 F:女 M:男 |
| `birth_year` | str | Y | 出生年份 |
| `edu` | str | Y | 学历 |
| `nationality` | str | Y | 国籍 |
| `begin_date` | str | Y | 任职日期 |
| `end_date` | str | Y | 离任日期 |
| `resume` | str | Y | 简历 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fund_manager",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "510300.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#初始接口
pro = ts.pro_api()

#单只基金
df = pro.fund_manager(ts_code='150018.SZ')

#多只基金
df = pro.fund_manager(ts_code='150018.SZ,150008.SZ')
```

## 实际返回示例（官方文档）

```text
ts_code  ann_date   name  gender birth_year edu nationality begin_date  end_date                                             resume
0  150018.SZ  20100508   周毅      M       None  硕士          美国   20100507      None  CFA，硕士学位；毕业于北京大学，美国南卡罗莱纳大学，美国约翰霍普金斯大学。曾任美国普华永道...
1  150018.SZ  20190831   张凯      M       None  硕士          中国   20190829      None  CFA，硕士学位，毕业于清华大学。2009年7月加盟银华基金管理有限公司，从事量化策略研发和...
2  150018.SZ  20100927  路志刚      M       1969  博士          中国   20100507  20100927  暨南大学金融学博士。曾任广东建设实业集团公司财务主管，广州证券有限公司发行部、营业部经理，金...
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fund_manager`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fund_manager.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
