# `index_member_all` — 申万行业成分构成(分级)

- 分类：指数专题
- 功能：按三级分类提取申万行业成分，可提供某个分类的所有成分，也可按股票代码提取所属分类，参数灵活
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需2000积分可调取，积分获取方法请参阅 积分获取办法
- 官方文档：[doc 335](https://tushare.pro/document/2?doc_id=335)
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
  "api_name": "index_member_all",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取黄金分类的成份股
df = pro.index_member_all(l3_code='850531.SI')

#获取000001.SZ所属行业
df = pro.index_member_all(ts_code='000001.SZ')
```

## 实际返回示例（官方文档）

```text
l1_code l1_name     l2_code       l2_name  l3_code     l3_name    ts_code       name   in_date
0   801050.SI    有色金属  801053.SI     贵金属  850531.SI      黄金  000506.SZ      *ST中润  20220729
1   801050.SI    有色金属  801053.SI     贵金属  850531.SI      黄金  001337.SZ       四川黄金  20230224
2   801050.SI    有色金属  801053.SI     贵金属  850531.SI      黄金  600988.SH       赤峰黄金  20040414
3   801050.SI    有色金属  801053.SI     贵金属  850531.SI      黄金  600489.SH       中金黄金  20030812
4   801050.SI    有色金属  801053.SI     贵金属  850531.SI      黄金  600547.SH       山东黄金  20030826
5   801050.SI    有色金属  801053.SI     贵金属  850531.SI      黄金  002155.SZ       湖南黄金  20070815
6   801050.SI    有色金属  801053.SI     贵金属  850531.SI      黄金  002237.SZ       恒邦股份  20080428
7   801050.SI    有色金属  801053.SI     贵金属  850531.SI      黄金  601069.SH       西部黄金  20150115
8   801050.SI    有色金属  801053.SI     贵金属  850531.SI      黄金  000975.SZ       银泰黄金  20190724
9   801050.SI    有色金属  801053.SI     贵金属  850531.SI      黄金  300139.SZ       晓程科技  20220729
10  801050.SI    有色金属  801053.SI     贵金属  850531.SI      黄金  600687.SH   退市刚泰(退市)  20130701
11  801050.SI    有色金属  801053.SI     贵金属  850531.SI      黄金  600807.SH       济南高新  20220729
12  801050.SI    有色金属  801053.SI     贵金属  850531.SI      黄金  600311.SH  *ST荣华(退市)  20140102
```

## claw-quant 存储契约

### 运行时分片契约

空参数全市场请求实测触及 3,000 行可疑上限，不能证明完整。系统先采集
`index_classify` 的 SW2014/SW2021 L3 分类，再从
`tushare_norm_index_classify.index_code` 白名单逐个作为 `l3_code` 扇出。
批次未覆盖完整宇宙前状态保持 `incomplete`。

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_index_member_all`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/index_member_all.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
