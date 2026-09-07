# `fund_basic` — 公募基金列表

- 分类：公募基金
- 功能：获取公募基金数据列表，包括场内和场外基金
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要2000积分才可以调取，单次最大可以提取15000条数据，5000积分以上权限更高，具体请参阅 积分获取办法
- 官方文档：[doc 19](https://tushare.pro/document/2?doc_id=19)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

运行时完整性说明：2026-09-06 实测 HTTP 网关支持文档参数表未列出的标准
`limit` / `offset`。`market=O,status=L` 在 0、5000、10000、15000、20000
偏移返回互不重复的页面，并在累计 24974 行后耗尽。初始化因此分别固定
`market=E` 与 `market=O` 两个互斥范围，再对每个范围分页至空页；任何页面重复或
达到最大页数仍会失败，不能把 15000 行上限误判为完整。

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 基金代码 |
| `market` | str | N | 交易市场: E场内 O场外（默认E） |
| `status` | str | N | 存续状态 D摘牌/已到期 I发行 L已上市/存续中 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 基金代码 |
| `name` | str | Y | 简称 |
| `management` | str | Y | 管理人 |
| `custodian` | str | Y | 托管人 |
| `fund_type` | str | Y | 投资类型 |
| `found_date` | str | Y | 成立日期 |
| `due_date` | str | Y | 到期日期 |
| `list_date` | str | Y | 上市时间 |
| `issue_date` | str | Y | 发行日期 |
| `delist_date` | str | Y | 退市日期 |
| `issue_amount` | float | Y | 发行份额(亿) |
| `m_fee` | float | Y | 管理费 |
| `c_fee` | float | Y | 托管费 |
| `duration_year` | float | Y | 存续期 |
| `p_value` | float | Y | 面值 |
| `min_amount` | float | Y | 起点金额(万元) |
| `exp_return` | float | Y | 预期收益率 |
| `benchmark` | str | Y | 业绩比较基准 |
| `status` | str | Y | 存续状态D摘牌/已到期 I发行 L已上市/存续中 |
| `invest_type` | str | Y | 投资风格 |
| `type` | str | Y | 基金类型 |
| `trustee` | str | Y | 受托人 |
| `purc_startdate` | str | Y | 日常申购起始日 |
| `redm_startdate` | str | Y | 日常赎回起始日 |
| `market` | str | Y | E场内O场外 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fund_basic",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "510300.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.fund_basic(market='E')
```

## 实际返回示例（官方文档）

```text
ts_code             name         management  custodian      fund_type found_date  \
1     512850.SH    中信建投北京50ETF     中信建投基金      招商银行       股票型   20180927
2     168601.SZ    汇安裕阳三年定期开放       汇安基金    中国光大银行       混合型   20180927
3     512860.SH    华安中国A股ETF       华安基金    中国农业银行       股票型   20180927
4     159960.SZ    恒生国企     平安大华基金      中国银行       股票型   20180921
5     501062.SH    南方瑞合三年       南方基金    中国建设银行       混合型   20180906
6     510600.SH    沪50ETF     申万菱信基金    中国工商银行       股票型   20180903
7     501061.SH    金选300C       中金基金    中国建设银行       股票型   20180830
8     501060.SH    金选300A       中金基金    中国建设银行       股票型   20180830
9     166802.SZ     浙商300       浙商基金      华夏银行       股票型   20180820
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fund_basic`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fund_basic.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
