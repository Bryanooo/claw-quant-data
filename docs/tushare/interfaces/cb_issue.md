# `cb_issue` — 可转债发行

- 分类：债券专题
- 功能：获取可转债发行数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，5000积分以上频次相对较高，积分越多权限越大，具体请参阅 积分获取办法
- 官方文档：[doc 186](https://tushare.pro/document/2?doc_id=186)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS代码 |
| `ann_date` | str | N | 发行公告日 |
| `start_date` | str | N | 公告开始日期 |
| `end_date` | str | N | 公告结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 转债代码 |
| `ann_date` | str | Y | 发行公告日 |
| `res_ann_date` | str | Y | 发行结果公告日 |
| `plan_issue_size` | float | Y | 计划发行总额（元） |
| `issue_size` | float | Y | 发行总额（元） |
| `issue_price` | float | Y | 发行价格 |
| `issue_type` | str | Y | 发行方式 |
| `issue_cost` | float | N | 发行费用（元） |
| `onl_code` | str | Y | 网上申购代码 |
| `onl_name` | str | Y | 网上申购简称 |
| `onl_date` | str | Y | 网上发行日期 |
| `onl_size` | float | Y | 网上发行总额（张） |
| `onl_pch_vol` | float | Y | 网上发行有效申购数量（张） |
| `onl_pch_num` | int | Y | 网上发行有效申购户数 |
| `onl_pch_excess` | float | Y | 网上发行超额认购倍数 |
| `onl_winning_rate` | float | N | 网上发行中签率（%） |
| `shd_ration_code` | str | Y | 老股东配售代码 |
| `shd_ration_name` | str | Y | 老股东配售简称 |
| `shd_ration_date` | str | Y | 老股东配售日 |
| `shd_ration_record_date` | str | Y | 老股东配售股权登记日 |
| `shd_ration_pay_date` | str | Y | 老股东配售缴款日 |
| `shd_ration_price` | float | Y | 老股东配售价格 |
| `shd_ration_ratio` | float | Y | 老股东配售比例 |
| `shd_ration_size` | float | Y | 老股东配售数量（张） |
| `shd_ration_vol` | float | N | 老股东配售有效申购数量（张） |
| `shd_ration_num` | int | N | 老股东配售有效申购户数 |
| `shd_ration_excess` | float | N | 老股东配售超额认购倍数 |
| `offl_size` | float | Y | 网下发行总额（张） |
| `offl_deposit` | float | N | 网下发行定金比例（%） |
| `offl_pch_vol` | float | N | 网下发行有效申购数量（张） |
| `offl_pch_num` | int | N | 网下发行有效申购户数 |
| `offl_pch_excess` | float | N | 网下发行超额认购倍数 |
| `offl_winning_rate` | float | N | 网下发行中签率 |
| `lead_underwriter` | str | N | 主承销商 |
| `lead_underwriter_vol` | float | N | 主承销商包销数量（张） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "cb_issue",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "110000.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()


#获取可转债发行数据
df = pro.cb_issue(ann_date='20190612')


#获取可转债发行数据，自定义字段
df = pro.cb_issue(fields='ts_code,ann_date,issue_size')
```

## 实际返回示例（官方文档）

```text
ts_code  ann_date issue_size
0    110072.SH  20200814    33.7000
1    113600.SH  20200811     5.9500
2    113598.SH  20200729     3.3000
3    113038.SH  20200729    50.0000
4    128125.SZ  20200728     4.5000
..         ...       ...        ...
489  100009.SH  20000223    13.5000
490  125302.SZ  19990727    15.0000
491  125301.SZ  19980826     2.0000
492  100001.SH  19980730     1.5000
493  125009.SZ      None     5.0000
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_cb_issue`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/cb_issue.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
