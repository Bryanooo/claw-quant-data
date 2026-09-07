# `ci_index_member` — 中信行业成分

- 分类：指数专题
- 功能：按三级分类提取中信行业成分，可提供某个分类的所有成分，也可按股票代码提取所属分类，参数灵活
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需5000积分可调取，积分获取方法请参阅 积分获取办法
- 官方文档：[doc 373](https://tushare.pro/document/2?doc_id=373)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `l1_code` | str | N | 一级行业代码 |
| `l2_code` | str | N | 二级行业代码 |
| `l3_code` | str | N | 三级行业代码 |
| `ts_code` | str | N | 股票代码 |
| `is_new` | str | N | 是否最新（默认为“Y是”） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `l1_code` | str | Y | 一级行业代码 |
| `l1_name` | str | Y | 一级行业名称 |
| `l2_code` | str | Y | 二级行业代码 |
| `l2_name` | str | Y | 二级行业名称 |
| `l3_code` | str | Y | 三级行业代码 |
| `l3_name` | str | Y | 三级行业名称 |
| `ts_code` | str | Y | 成分股票代码 |
| `name` | str | Y | 成分股票名称 |
| `in_date` | str | Y | 纳入日期 |
| `out_date` | str | Y | 剔除日期 |
| `is_new` | str | Y | 是否最新Y是N否 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "ci_index_member",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取二级分类元器件的成份股
df = pro.ci_index_member(l2_code='CI005835.CI', fields='l2_code,l1_name,ts_code,name')

#获取000001.SZ所属行业
df = pro.ci_index_member(ts_code='000001.SZ')
```

## 实际返回示例（官方文档）

```text
l2_code     l1_name  ts_code       name
0   CI005835.CI      电子  301628.SZ       强达电路
1   CI005835.CI      电子  920060.BJ        万源通
2   CI005835.CI      电子  301251.SZ        威尔高
3   CI005835.CI      电子  002552.SZ       宝鼎科技
4   CI005835.CI      电子  301566.SZ       达利凯普
5   CI005835.CI      电子  688519.SH       南亚新材
6   CI005835.CI      电子  603920.SH       世运电路
7   CI005835.CI      电子  603936.SH       博敏电子
8   CI005835.CI      电子  603989.SH       艾华集团
9   CI005835.CI      电子  688020.SH       方邦股份
10  CI005835.CI      电子  300852.SZ       四会富仕
11  CI005835.CI      电子  688655.SH        迅捷兴
12  CI005835.CI      电子  688183.SH       生益电子
13  CI005835.CI      电子  301132.SZ       满坤科技
14  CI005835.CI      电子  001389.SZ       广合科技
15  CI005835.CI      电子  002288.SZ  *ST超华(退市)
16  CI005835.CI      电子  600563.SH       法拉电子
17  CI005835.CI      电子  603186.SH       华正新材
18  CI005835.CI      电子  603228.SH       景旺电子
19  CI005835.CI      电子  603328.SH       依顿电子
20  CI005835.CI      电子  000636.SZ       风华高科
21  CI005835.CI      电子  000823.SZ       超声电子
22  CI005835.CI      电子  002134.SZ       天津普林
23  CI005835.CI      电子  002138.SZ       顺络电子
24  CI005835.CI      电子  002199.SZ      *ST东晶
25  CI005835.CI      电子  002436.SZ       兴森科技
26  CI005835.CI      电子  002463.SZ       沪电股份
27  CI005835.CI      电子  002484.SZ       江海股份
28  CI005835.CI      电子  002579.SZ       中京电子
29  CI005835.CI      电子  002618.SZ    丹邦退(退市)
30  CI005835.CI      电子  002636.SZ       金安国纪
31  CI005835.CI      电子  300814.SZ       中富电路
32  CI005835.CI      电子  300964.SZ       本川智能
33  CI005835.CI      电子  002815.SZ       崇达技术
34  CI005835.CI      电子  002859.SZ       洁美科技
35  CI005835.CI      电子  002913.SZ        奥士康
36  CI005835.CI      电子  002916.SZ       深南电路
37  CI005835.CI      电子  301366.SZ       一博科技
38  CI005835.CI      电子  300319.SZ       麦捷科技
39  CI005835.CI      电子  300408.SZ       三环集团
40  CI005835.CI      电子  300476.SZ       胜宏科技
41  CI005835.CI      电子  688630.SH       芯碁微装
42  CI005835.CI      电子  300975.SZ       商络电子
43  CI005835.CI      电子  837821.BJ       则成电子
44  CI005835.CI      电子  871981.BJ       晶赛科技
45  CI005835.CI      电子  300657.SZ       弘信电子
46  CI005835.CI      电子  301282.SZ       金禄电子
47  CI005835.CI      电子  300739.SZ       明阳电路
48  CI005835.CI      电子  600183.SH       生益科技
49  CI005835.CI      电子  600237.SH       铜峰电子
50  CI005835.CI      电子  603386.SH       骏亚科技
51  CI005835.CI      电子  605258.SH       协和电子
52  CI005835.CI      电子  300903.SZ       科翔股份
53  CI005835.CI      电子  605058.SH       澳弘电子
54  CI005835.CI      电子  301041.SZ        金百泽
```

## claw-quant 存储契约

### 运行时分片契约

空参数全市场请求实测触及 5,000 行可疑上限，不能证明完整。系统仅允许
通过受控扇出入口，从 `tushare_norm_ci_daily.ts_code` 的本地中信行业
指数宇宙取值，逐个作为 `l3_code` 采集。部分非 L3 指数返回空数据是
可审计的预期结果；批次未覆盖完整宇宙前状态保持 `incomplete`。

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_ci_index_member`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/ci_index_member.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
