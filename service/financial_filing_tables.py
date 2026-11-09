"""Verify current-column filing values against the separately sourced same disclosure."""
import hashlib
from pathlib import Path
import re
from decimal import Decimal

from service.financial_filing_evidence import NUMBER, UNITS

_UNIT = r'(百万元|千元|万元|元)'
_PROFIT = '归属于上市公司股东的净利润'
_TOTAL = ('所有者权益（或股东权益）合计', '所有者权益合计', '股东权益合计')
_PARENT = ('归属于母公司所有者权益（或股东权益）合计', '归属于母公司所有者权益合计',
           '归属于母公司股东权益合计')


def read_verified_pdf_pages(path, sha256):
    import pypdfium2 as pdf

    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError('original file digest mismatch')
    pages = []
    with pdf.PdfDocument(raw) as reader:
        for i in range(len(reader)):
            page = reader[i]
            text = page.get_textpage()
            try:
                pages.append(text.get_text_bounded().replace('\r', ''))
            finally:
                text.close()
                page.close()
    return pages


def _spaced(label):
    return r'\s*'.join(re.escape(c) for c in label)


def _entries(text, labels):
    # Wrapped labels may cross lines, but a preceding label on the same line
    # (e.g. parent equity) must never be consumed as a total-equity match.
    for label in labels:
        pattern = (r'(?m)^[ \t]*' + _spaced(label)
                   + r'(?:\s*[（(](?:人民币)?' + _UNIT + r'[）)])?\s+'
                   + '(' + NUMBER + r')(?![\d,.])\s+(' + NUMBER + r')(?![\d,.])')
        for m in re.finditer(pattern, text):
            yield label, m


def _unit_before(text, printed):
    # Reports can print just “元” on a line above the columns. Keep units
    # local to the nearest declaration, including unsupported currencies.
    declarations = re.findall(
        r'(?m)^[ \t]*(?:(?:金额)?单位[ \t]*[：:][ \t]*([^\s，,；;]+)'
        r'|((?:人民币)?(?:百万元|千元|万元|元))(?=[ \t]*$))', text)
    currencies = re.findall(r'币种[ \t]*[：:][ \t]*([^\s，,；;]+)', text)
    if currencies and currencies[-1] != '人民币':
        raise ValueError('table_currency_unproven')
    if not printed and not declarations:
        raise ValueError('table_unit_unproven')
    last = next(filter(None, declarations[-1]), '') if declarations else ''
    if last and not re.fullmatch(r'(?:人民币)?' + _UNIT, last):
        raise ValueError('table_unit_unproven')
    return '人民币' + (printed or last.removeprefix('人民币'))


def _verified(pages, first, last, labels, expected, header, *, comparison=None):
    seen = []
    for index in range(first, last + 1):
        page = pages[index]
        for label, match in _entries(page, labels):
            preceding = '\n'.join([*pages[first:index], page[:match.start()]])
            compact = ''.join(preceding.split())
            if not header(compact):
                continue
            unit = _unit_before(preceding, match[1])
            current, prior = [Decimal(match[i].replace(',', '')) * UNITS[unit] for i in (2, 3)]
            if current != Decimal(expected):
                continue
            if comparison is not None:
                # A restated table may put the original comparative first. It
                # cannot establish that the current and prior periods agree.
                if '调整前' in compact[-800:] or '调整后' in compact[-800:] or '（已重述）' in compact[-800:] or '(已重述)' in compact[-800:]:
                    raise ValueError('restated_comparative_requires_review')
                if prior != Decimal(comparison):
                    raise ValueError('comparison_version_mismatch')
            seen.append(dict(page=index+1, label=label, unit=unit, current=str(current),
                             comparative=str(prior)))
    if len(seen) != 1:
        raise ValueError('current_column_not_uniquely_corroborated')
    return seen[0]


def _section(pages, heading, next_headings):
    section = []
    first = None
    prefix = r'(?m)^[\d一二三四、.．（）() \t]*'
    for index, text in enumerate(pages):
        if first is None:
            match = re.search(prefix + heading + r'[ \t]*$', text)
            if not match:
                continue
            first = index
            text = text[match.end():]
        stop = re.search(prefix + '(?:' + '|'.join(next_headings) + r')[ \t]*$', text)
        section.append(text[:stop.start()] if stop else text)
        if stop:
            break
    if first is None:
        raise ValueError('missing_' + heading)
    return first, section


def verify_tables(pages, *, code, issuer, period, income, balance=None, comparison=None):
    """Read the issuer summary and (when needed) the consolidated balance sheet.

    The catalog has already pinned issuer, exact disclosure date and report type.
    Use only the current amount and reject older-period restatements. No fact is
    emitted solely because a particular number appears somewhere in the PDF.
    """
    cover = ''.join(''.join(pages[:2]).split())
    year = period[:4]
    annual = period.endswith('12-31')
    half = period.endswith('06-30')
    interim = '半年度' if half else '第一季度'
    title = year + ('年年度报告' if annual else '年' + interim + '报告')
    titles = [title, title.replace('年年度', '年度'),title.replace('第一季度', '一季度')]
    if not any(t in cover for t in titles) or not (code in cover or (issuer and issuer in cover)):
        raise ValueError('issuer_or_period_unproven')
    def income_header(s):
        if annual:
            return year+'年' in s and str(int(year)-1)+'年' in s and (
                '本年比上年' in s or '本期比上年' in s or '本年末比上年末' in s)
        return '本报告期' in s and '上年同期' in s

    # Annual full reports contain the same summary, usually after the contents.
    end = min(len(pages),45 if annual or half else 6)-1
    try:
        profit = _verified(pages, 0, end, [_PROFIT, '归属于母公司股东的净利润'],
                           income, income_header, comparison=comparison)
    except ValueError as error:
        if str(error) not in {'current_column_not_uniquely_corroborated', 'table_unit_unproven'}:
            raise
        # The summary may round to millions while the statement prints yuan.
        try:
            start, section = _section(pages, '合并利润表', ('母公司利润表', '合并现金流量表'))
        except ValueError:
            raise ValueError('summary_' + str(error) + '_and_no_consolidated_income_table') from error
        base = '归属于母公司股东的净利润'
        labels = [base, '1.' + base, '归属于母公司所有者的净利润']
        for mark in ('-', '－', '—', '–'):
            labels.append('1.' + base + '（净亏损以“' + mark + '”号填列）')
        def statement_header(s):
            date_columns = ((year + '年度' in s and str(int(year)-1) + '年度' in s)
                            if annual else
                            (year + '年' + interim in s and str(int(year)-1) + '年' + interim in s))
            return date_columns or ('本期发生额' in s and '上期发生额' in s
                                    and year + '年' in s)
        profit = _verified(section, 0, len(section)-1, labels, income,
                           statement_header, comparison=comparison)
        profit['page'] += start
    fields = [('n_income_attr_p', profit)]
    if balance is None:
        return fields
    fields.extend(verify_equity_rows(pages, period, balance))
    return fields


def verify_equity_rows(pages, period, balance):
    """Read only the named consolidated interim balance sheet for this period."""
    year = period[:4]
    month = int(period[5:7])
    if period[5:] not in ('03-31','06-30','09-30'):
        raise ValueError('unsupported interim balance period')
    fields = []
    start, section = _section(pages, '合并资产负债表',
                              ('母公司资产负债表','合并利润表','合并现金流量表'))
    def balance_header(s):
        if '项目期末余额期初余额' in s and not re.search(r'20\d{2}年\d{1,2}月\d{1,2}日', s):
            return True  # Current/opening columns in the identified interim consolidated statement.
        day = int(period[8:])
        end_dates = (f'年{month}月{day}日', f'年{month:02}月{day:02}日')
        return any(year + ending in s for ending in end_dates) and (
            str(int(year)-1)+'年12月31日' in s or '期末余额期初余额' in s)
    def equity(labels, expected):
        row = _verified(section,0,len(section)-1,labels,expected,balance_header)
        row['page'] += start
        return row
    total = balance['total_hldr_eqy_inc_min_int']
    fields.append(('total_hldr_eqy_inc_min_int',equity(_TOTAL,total)))
    if balance.get('minority_int') is None or Decimal(balance['minority_int']) == 0:
        # Even if the minority cell is blank, establish equality independently.
        fields.append(('total_hldr_eqy_exc_min_int',equity(_PARENT,total)))
    else:
        fields.append(('minority_int',equity(['少数股东权益'],balance['minority_int'])))
    return fields
