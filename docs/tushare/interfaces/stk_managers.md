# `stk_managers` — 上市公司管理层

- 分类：股票数据/基础数据
- 功能：获取上市公司管理层
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要2000积分才可以调取，5000积分以上频次相对较高，具体请参阅 积分获取办法
- 官方文档：[doc 193](https://tushare.pro/document/2?doc_id=193)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/basic/stk_managers.py:StkManagersCollector](../../../collectors/stock/basic/stk_managers.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码，支持单个或多个股票输入 |
| `ann_date` | str | N | 公告日期（YYYYMMDD格式，下同） |
| `start_date` | str | N | 公告开始日期 |
| `end_date` | str | N | 公告结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS股票代码 |
| `ann_date` | str | Y | 公告日期 |
| `name` | str | Y | 姓名 |
| `gender` | str | Y | 性别 |
| `lev` | str | Y | 岗位类别 |
| `title` | str | Y | 岗位 |
| `edu` | str | Y | 学历 |
| `national` | str | Y | 国籍 |
| `birthday` | str | Y | 出生年月 |
| `begin_date` | str | Y | 上任日期 |
| `end_date` | str | Y | 离任日期 |
| `resume` | str | N | 个人简历 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stk_managers",
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
df = pro.stk_managers(ts_code='000001.SZ')

#获取多个公司高管全部数据
df = pro.stk_managers(ts_code='000001.SZ,600000.SH')
```

## 实际返回示例（官方文档）

```text
ts_code  ann_date     name    gender  ... national  birthday begin_date  end_date
0    000001.SZ  20190604  姚贵平      M  ...       中国     1961   20180815  20190604
1    000001.SZ  20190604  姚贵平      M  ...       中国     1961   20170629  20190604
2    000001.SZ  20190604  姚贵平      M  ...       中国     1961   20180129  20190604
3    000001.SZ  20190309   吴鹏      M  ...       中国     1965   20110817  20190309
4    000001.SZ  20190307  孙永桢      F  ...       中国     1968   20181025      None
5    000001.SZ  20180816  杨志群      M  ...       中国     1970   20180815      None
6    000001.SZ  20180816  郭世邦      M  ...       中国     1965   20180815      None
7    000001.SZ  20180405  何之江      M  ...       中国     1965   20170513  20180405
8    000001.SZ  20180203  项有志      M  ...       中国     1964   20170913      None
9    000001.SZ  20180130  杨如生      M  ...       中国   196802   20161107      None
10   000001.SZ  20180130  蔡方方      F  ...       中国     1974   20161107      None
11   000001.SZ  20180130  郭田勇      M  ...       中国   196808   20161107      None
12   000001.SZ  20180130   郭建      M  ...       中国     1964   20161107      None
13   000001.SZ  20180130  杨如生      M  ...       中国   196802   20161107      None
14   000001.SZ  20180130  杨如生      M  ...       中国   196802   20161107      None
15   000001.SZ  20180130   姚波      M  ...       中国     1971   20101227      None
16   000001.SZ  20180130  王春汉      M  ...       中国     1951   20160811      None
17   000001.SZ  20180130  郭田勇      M  ...       中国   196808   20160811      None
18   000001.SZ  20180130  郭田勇      M  ...       中国   196808   20160811      None
19   000001.SZ  20180130  韩小京      M  ...       中国     1955   20140121      None
20   000001.SZ  20180130  陈心颖      F  ...      新加坡     1977   20140121      None
21   000001.SZ  20180130  蔡方方      F  ...       中国     1974   20140121      None
22   000001.SZ  20180130  王松奇      M  ...       中国     1952   20140121      None
23   000001.SZ  20180130  王春汉      M  ...       中国     1951   20140121      None
24   000001.SZ  20180130  韩小京      M  ...       中国     1955   20140121      None
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
