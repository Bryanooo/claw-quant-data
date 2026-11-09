from datetime import date

import pytest

from service.financial_filing_facts import original_filing_source
from service.financial_filing_tables import verify_tables


def test_million_yuan_and_exact_current_amount():
    pages = ['证券代码 600000 2025年年度报告摘要\n单位：百万元\n'
             '2025年 2024年 本年比上年增减 2023年\n'
             '归属于上市公司股东的\n净利润 12 11 9.09% 10']
    result = verify_tables(pages, code='600000',issuer='浦发银行',period='2025-12-31',income='12000000')
    assert result[0][1]['current'] == '12000000'
    assert result[0][1]['unit'] == '人民币百万元'
    with pytest.raises(ValueError):
        verify_tables(pages,code='600000',issuer='',period='2025-12-31',income='11000000')


def test_restatement_question_does_not_imply_restatement_but_adjusted_columns_do():
    preamble = '600000 2026年第一季度报告\n是否需追溯调整或重述以前年度会计数据：否\n单位：元\n本报告期 上年同期'
    label = '\n归属于上市公司股东的净利润 12 11 10'
    verify_tables([preamble+label],code='600000',issuer='',period='2026-03-31',income='12',comparison='11')
    with pytest.raises(ValueError,match='restated'):
        verify_tables([preamble+' 调整前 调整后'+label],code='600000',issuer='',
                      period='2026-03-31',income='12',comparison='11')


def test_exchange_original_url_is_bound_to_its_host_and_disclosure_date():
    url = ('https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-04-30/'
           '80385b2b-c295-4a3c-bca4-6e6843a497ef.PDF')
    assert original_filing_source(url,date(2026,4,30)) == 'szse'
    assert original_filing_source(url,date(2026,4,29)) is None
    assert original_filing_source(url.replace('.cn/', '.cn.example/'),date(2026,4,30)) is None


def test_standalone_unit_and_explicit_currency_in_financial_summary():
    page = ('600000 2025年年度报告摘要\n元\n2025年 2024年 本年比上年增减\n'
            '归属于上市公司股东的净利润 12 11 10')
    args = dict(code='600000', issuer='', period='2025-12-31', income='12')
    assert verify_tables([page], **args)[0][1]['current'] == '12'
    for declaration in ('单位：美元', '单位：美元 币种：美元', '单位：元 币种：港币'):
        with pytest.raises(ValueError):
            verify_tables([page.replace('元\n', '元\n'+declaration+'\n')], **args)


def test_consolidated_q1_closing_and_opening_columns_prove_direct_parent():
    page = ('600000 2026年第一季度报告\n单位：元\n本报告期 上年同期\n'
            '归属于上市公司股东的净利润 12 11\n1、合并资产负债表\n'
            '单位：元\n项目 期末余额 期初余额\n归属于母公司所有者权益合计 80 75\n'
            '所有者权益合计 80 75')
    rows = dict(verify_tables([page], code='600000', issuer='', period='2026-03-31', income='12',
                              balance={'total_hldr_eqy_inc_min_int': '80'}))
    assert rows['total_hldr_eqy_exc_min_int']['current'] == '80'


def test_half_year_requires_matching_cover_and_june_balance_columns():
    pages = ['600000 2026年半年度报告\n单位：元\n本报告期 上年同期\n'
             '归属于上市公司股东的净利润 12 11\n合并资产负债表\n'
             '单位：元\n2026年6月30日 2025年12月31日\n'
             '所有者权益合计 80 75\n少数股东权益 10 9']
    args = dict(code='600000',issuer='',period='2026-06-30',income='12',comparison='11',
                balance={'total_hldr_eqy_inc_min_int':'80','minority_int':'10'})
    assert len(verify_tables(pages, **args)) == 3
    with pytest.raises(ValueError):
        verify_tables([pages[0].replace('6月30日','3月31日')], **args)


def test_later_full_report_blocks_older_annual_summary_before_cutoff():
    from service.financial_filing_catalog import select_lag_documents
    period = '2025-12-31'
    target = dict(ts_code='000001.SZ',fullname='示例',periods=[period],
                  docs={period:{'income':{'pub':'2026-04-27','n_income_attr_p':'12'}}})
    rows = {'a':dict(title='2025年年度报告摘要',date='2026-04-27'),
            'b':dict(title='2025年年度报告（更正后）',date='2026-07-22')}
    catalog = {'000001.SZ': rows}
    assert select_lag_documents(target, catalog, '2026-07-29') is None
    assert select_lag_documents(target, catalog, '2026-07-22')['documents'][0]['period'] == period
