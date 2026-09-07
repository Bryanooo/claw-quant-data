# `stk_rewards` — 管理层薪酬和持股

- 分类：股票数据/基础数据
- 功能：获取上市公司管理层薪酬和持股
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要2000积分才可以调取，5000积分以上频次相对较高，具体请参阅 积分获取办法
- 官方文档：[doc 194](https://tushare.pro/document/2?doc_id=194)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/basic/stk_rewards.py:StkRewardsCollector](../../../collectors/stock/basic/stk_rewards.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS股票代码，支持单个或多个代码输入 |
| `end_date` | str | N | 报告期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS股票代码 |
| `ann_date` | str | Y | 公告日期 |
| `end_date` | str | Y | 截止日期 |
| `name` | str | Y | 姓名 |
| `title` | str | Y | 职务 |
| `reward` | float | Y | 报酬 |
| `hold_vol` | float | Y | 持股数 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stk_rewards",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SZ"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

#获取单个公司高管全部数据
df = pro.stk_rewards(ts_code='000001.SZ')

#获取多个公司高管全部数据
df = pro.stk_rewards(ts_code='000001.SZ,600000.SH')
```

## 实际返回示例（官方文档）

```text
ts_code    ann_date  end_date      name     title     reward  hold_vol
0    000001.SZ  20190808  20190630  谢永林       董事长        NaN       0.0
1    000001.SZ  20190808  20190630  胡跃飞     董事,行长        NaN    4104.0
2    000001.SZ  20190808  20190630  陈心颖        董事        NaN       0.0
3    000001.SZ  20190808  20190630   姚波        董事        NaN       0.0
4    000001.SZ  20190808  20190630  叶素兰        董事        NaN       0.0
5    000001.SZ  20190808  20190630  韩小京      独立董事        NaN       0.0
6    000001.SZ  20190808  20190630  蔡方方        董事        NaN       0.0
7    000001.SZ  20190808  20190630   郭建        董事        NaN       0.0
8    000001.SZ  20190808  20190630  郭世邦    董事,副行长        NaN       0.0
9    000001.SZ  20190808  20190630  王春汉      独立董事        NaN       0.0
10   000001.SZ  20190808  20190630  王松奇      独立董事        NaN       0.0
11   000001.SZ  20190808  20190630  郭田勇      独立董事        NaN       0.0
12   000001.SZ  20190808  20190630  杨如生      独立董事        NaN       0.0
13   000001.SZ  20190808  20190630   邱伟  监事长,职工监事        NaN       0.0
14   000001.SZ  20190808  20190630  车国宝      股东监事        NaN       0.0
15   000001.SZ  20190808  20190630  周建国      外部监事        NaN       0.0
16   000001.SZ  20190808  20190630  骆向东      外部监事        NaN       0.0
17   000001.SZ  20190808  20190630  储一昀      外部监事        NaN       0.0
18   000001.SZ  20190808  20190630  孙永桢      职工监事        NaN       0.0
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
