# `mkt_idx_bmk` — 公募基金业绩基准库

- 分类：公募基金
- 功能：获取官方发布的ETF业绩比较基准列表信息，分为一类库、二类库
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：需要5000积分可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 462](https://tushare.pro/document/2?doc_id=462)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 指数代码 |
| `bmk_type` | str | N | 基准类型：策略指数、行业主题指数、行业主题指数、宽基指数 |
| `bmk_level` | str | N | 基准分类： 一类库、二类库 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `symbol` | str | Y | 代码 |
| `name` | str | Y | 指数简称 |
| `fullname` | str | Y | 指数名称 |
| `bmk_level` | str | Y | 基准库分层 一类库、二类库 |
| `bmk_type` | str | Y | 基准类型 策略、宽基、行业主题 |
| `bmk_src` | str | Y | 指数编制机构 |
| `idx_type` | str | Y | 指数类型 策略类指数；规模类指数；主题类指数；综合类指数；行业类指数；风格类指数 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "mkt_idx_bmk",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "510300.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取上证指数
df = pro.mkt_idx_bmk(ts_code='000001.SH')

#获取宽基指数
df = pro.mkt_idx_bmk(bmk_type='宽基')

#获取一类库数据
df = pro.mkt_idx_bmk(bmk_level='一类库')
```

## 实际返回示例（官方文档）

```text
ts_code  symbol    name      fullname bmk_level bmk_type bmk_src idx_type
0   000001.SH  000001    上证指数        上证综合指数       一类库       宽基    中证指数    综合类指数
1   000002.SH  000002    A股指数        上证A股指数       二类库       宽基    中证指数    规模类指数
2   000010.SH  000010   上证180       上证180指数       二类库       宽基    中证指数    规模类指数
3   000015.SH  000015    红利指数        上证红利指数       二类库       策略    中证指数    策略类指数
4   000016.SH  000016    上证50        上证50指数       一类库       宽基    中证指数    规模类指数
5   000097.SH  000097    高端装备  上证高端装备制造60指数       二类库     行业主题    中证指数    主题类指数
6  000171.CSI  000171    新兴成指  中国战略新兴产业成份指数       一类库     行业主题    中证指数    主题类指数
7   000300.SH  000300   沪深300       沪深300指数       一类库       宽基    中证指数    规模类指数
8   000510.SH  000510  中证A500      中证A500指数       一类库       宽基    中证指数    规模类指数
9   000680.SH  000680    科创综指     上证科创板综合指数       一类库       宽基    中证指数    综合类指数
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_mkt_idx_bmk`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/mkt_idx_bmk.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
