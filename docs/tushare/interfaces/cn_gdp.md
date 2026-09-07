# `cn_gdp` — GDP数据

- 分类：宏观经济/国内宏观/国民经济
- 功能：获取国民经济之GDP数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积累600积分可以使用，具体请参阅 积分获取办法
- 官方文档：[doc 227](https://tushare.pro/document/2?doc_id=227)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `q` | str | N | 季度（2019Q1表示，2019年第一季度） |
| `start_q` | str | N | 开始季度 |
| `end_q` | str | N | 结束季度 |
| `fields` | str | N | 指定输出字段（e.g. fields='quarter,gdp,gdp_yoy'） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `quarter` | str | Y | 季度 |
| `gdp` | float | Y | GDP累计值（亿元） |
| `gdp_yoy` | float | Y | 当季同比增速（%） |
| `pi` | float | Y | 第一产业累计值（亿元） |
| `pi_yoy` | float | Y | 第一产业同比增速（%） |
| `si` | float | Y | 第二产业累计值（亿元） |
| `si_yoy` | float | Y | 第二产业同比增速（%） |
| `ti` | float | Y | 第三产业累计值（亿元） |
| `ti_yoy` | float | Y | 第三产业同比增速（%） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "cn_gdp",
  "token": "${TUSHARE_TOKEN}",
  "params": {},
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.cn_gdp(start_q='2018Q1', end_q='2019Q3')


#获取指定字段
df = pro.cn_gdp(start_q='2018Q1', end_q='2019Q3', fields='quarter,gdp,gdp_yoy')
```

## 实际返回示例（官方文档）

```text
quarter          gdp gdp_yoy          pi pi_yoy           si si_yoy           ti ti_yoy
0    2019Q4  990865.1000    6.10  70466.7000   3.10  386165.3000   5.70  534233.1000   6.90
1    2019Q3  712845.4000    6.20  43005.0000   2.90  276912.5000   5.60  392927.9000   7.00
2    2019Q2  460636.7000    6.30  23207.0000   3.00  179122.1000   5.80  258307.5000   7.00
3    2019Q1  218062.8000    6.40   8769.4000   2.70   81806.5000   6.10  127486.9000   7.00
4    2018Q4  900309.5000    6.60  64734.0000   3.50  366000.9000   5.80  469574.6000   7.60
..      ...          ...     ...         ...    ...          ...    ...          ...    ...
147  1956Q4    1028.0000   15.00    443.9000   4.70     280.7000  34.50     303.4000  14.10
148  1955Q4     910.0000    6.80    421.0000   7.90     222.2000   7.60     266.8000   4.60
149  1954Q4     859.0000    4.20    392.0000   1.70     211.7000  15.70     255.3000  -0.60
150  1953Q4     824.0000   15.60    378.0000   1.90     192.5000  35.80     253.5000  27.30
151  1952Q4     679.0000    None    342.9000   None     141.8000   None     194.3000   None
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_cn_gdp`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/cn_gdp.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
