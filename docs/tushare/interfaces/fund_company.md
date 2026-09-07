# `fund_company` — 公募基金公司

- 分类：公募基金
- 功能：获取公募基金管理人列表
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要1500积分才可以调取，一次可以提取全部数据。具体请参阅 积分获取办法
- 官方文档：[doc 118](https://tushare.pro/document/2?doc_id=118)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

当前官方目录没有可提取的输入参数表；调用时仍由 Tushare 服务端完成最终校验。

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `name` | str | Y | 基金公司名称 |
| `shortname` | str | Y | 简称 |
| `short_enname` | str | N | 英文缩写 |
| `province` | str | Y | 省份 |
| `city` | str | Y | 城市 |
| `address` | str | Y | 注册地址 |
| `phone` | str | Y | 电话 |
| `office` | str | Y | 办公地址 |
| `website` | str | Y | 公司网址 |
| `chairman` | str | Y | 法人代表 |
| `manager` | str | Y | 总经理 |
| `reg_capital` | float | Y | 注册资本 |
| `setup_date` | str | Y | 成立日期 |
| `end_date` | str | Y | 公司终止日期 |
| `employees` | float | Y | 员工总数 |
| `main_business` | str | Y | 主要产品及业务 |
| `org_code` | str | Y | 组织机构代码 |
| `credit_code` | str | Y | 统一社会信用代码 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fund_company",
  "token": "${TUSHARE_TOKEN}",
  "params": {},
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.fund_company()
```

## 实际返回示例（官方文档）

```text
name shortname   province       city
0      工银瑞信基金管理有限公司    工银瑞信基金        北京市        北京市
1      建信基金管理有限责任公司      建信基金        北京市        北京市
2        华商基金管理有限公司      华商基金        北京市        北京市
3    中邮创业基金管理股份有限公司      中邮基金        北京市        北京市
4      中国国际金融股份有限公司      中金公司        北京市        北京市
..              ...       ...        ...        ...
198      汇贤房托管理有限公司    汇贤房托管理  中国香港特别行政区  中国香港特别行政区
199      富豪资产管理有限公司    富豪资产管理  中国香港特别行政区  中国香港特别行政区
200      小飞资产管理有限公司    小飞资产管理  中国香港特别行政区  中国香港特别行政区
201        领航集团有限公司      领航集团       None         境外
202  辉立资本管理(香港)有限公司    辉立资本香港       None         境外
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fund_company`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fund_company.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
