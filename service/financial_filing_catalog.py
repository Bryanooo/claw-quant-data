"""Select a single interim/annual disclosure version from the SZSE announcement catalog."""
from collections import defaultdict
from datetime import date
import re


def index_szse_announcements(announcements):
    by_symbol = defaultdict(dict)
    for row in announcements:
        path = row.get('attachPath') or ''
        match = re.fullmatch(r'/disc/disk\d+/finalpage/(\d{4}-\d{2}-\d{2})/[\da-fA-F-]+\.PDF', path, re.I)
        published = (row.get('publishTime') or '')[:10]
        identifier = str(row.get('annId') or '')
        if not match or not published or published > match[1] or not identifier.isdecimal():
            continue
        disclosure = date.fromisoformat(match[1]).isoformat()
        url = f'https://static.cninfo.com.cn/finalpage/{disclosure}/{identifier}.PDF'
        for code in row.get('secCode') or ():
            if re.fullmatch(r'\d{6}', code):
                by_symbol[code + '.SZ'][url] = dict(url=url, date=disclosure,
                                                    title=row['title'], kb=row.get('attachSize') or 0)
    return by_symbol


def select_lag_documents(target, catalog, cutoff):
    """Supply catalog rows through cutoff, including corrections to previous filings."""
    code = target['ts_code']
    reports = []
    for period in target['periods']:
        annual = period.endswith('12-31')
        half = period.endswith('06-30')
        year = period[:4]
        family = (r'(?:年?年度报告|年报)' if annual else
                  (r'年(?:半年度报告|半年报|中期报告)' if half else r'年第?一季(?:度报告|报)'))
        summary = annual or (half and period == target['periods'][0])
        income = target['docs'][period]['income']
        def relevant(entry):
            title = entry['title']
            return (entry['date'] < cutoff and re.search(year + family, title)
                    and not re.search('英文|英语|H股', title))
        family_rows = [r for r in catalog.get(code, {}).values() if relevant(r)]
        # A correction to the full report can supersede an unchanged summary.
        # Notices mentioning cancellations or corrections must also trigger review.
        if not family_rows or any(r['date'] > income['pub'] for r in family_rows):
            return None
        candidates = [r for r in family_rows if r['date'] == income['pub']
                      and ('摘要' in r['title']) == summary
                      and not re.search('更新前|更正前|取消|关于|提示性|更正公告|说明', r['title'])]
        if len(candidates) != 1:
            return None
        reports.append(dict(candidates[0], period=period, published_on=income['pub'],
                            n_income_attr_p=income['n_income_attr_p'],
                            balance=target['docs'][period].get('balancesheet')))
    return dict(symbol=code, issuer=target['fullname'], cutoff=cutoff, documents=reports)
