"""Strict extraction of reviewed, two-column filing rows into evidence only.

This is deliberately not a general PDF-to-financial-table importer. Scope,
currency, column dates and publication metadata need review; ambiguous layouts
fail closed. Extracted facts never mutate Tushare rows or certify PIT globally.
"""
from decimal import Decimal
import re

NUMBER = r'-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
UNITS = {'人民币元': Decimal(1), '人民币千元': Decimal(1000), '人民币万元': Decimal(10000),
         '人民币百万元': Decimal(1000000)}


def extract_two_column_row(text, label, *, unit):
    if unit not in UNITS:
        raise ValueError('unverified filing unit')
    literal = r'\s*'.join(re.escape(c) for c in label)
    matches = re.findall(r'^\s*'+literal+r'\s+('+NUMBER+r')\s+('+NUMBER+r')\s*$', text, re.M)
    if len(matches) != 1:
        raise ValueError('expected exactly one unambiguous two-column row')
    current, comparative = [Decimal(s.replace(',',''))*UNITS[unit] for s in matches[0]]
    return {'current':current, 'comparative':comparative, 'label':label, 'unit':unit,
            'status':'extracted_requires_scope_and_version_review'}
