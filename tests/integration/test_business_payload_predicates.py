"""Exercise ready-label corruption against independent SQL value predicates."""
import os
from psycopg2 import sql
from psycopg2.extras import Json
import pytest

from service.data_coverage.business_predicates import business_predicate
from service.db import get_conn
from service.research.local_factors.catalog import FACTOR_SPECS
from service.research.local_factors.materializer import FORMULA_DIGEST

pytestmark = pytest.mark.skipif(os.getenv('RUN_DB_INTEGRATION') != '1',reason='requires PostgreSQL')


def test_local_factor_ready_mask_must_match_values_and_exclusions():
    conn=get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('CREATE TEMP TABLE payload (formula_digest text,factor_values float8[],ready_mask bit(272),ready_count int,audit_evidence jsonb)')
            cur.execute('INSERT INTO payload VALUES (%s,%s,%s,272,%s)',
                        (FORMULA_DIGEST,[1.0]*272,'1'*272,Json({'status':'ready','unresolved':{},'excluded':{}})))
            def valid():
                cur.execute(sql.SQL('SELECT COALESCE(({}),false) FROM payload').format(business_predicate('local_factor_snapshot')))
                return cur.fetchone()[0]
            assert valid()
            cur.execute('SAVEPOINT short_history')
            cur.execute("UPDATE payload SET audit_evidence=audit_evidence || jsonb_build_object('listing_sessions_observed',20)")
            assert not valid()
            cur.execute('ROLLBACK TO SAVEPOINT short_history')
            for change in ("factor_values[1]='NaN'::float8", "factor_values[1]=NULL",
                           "ready_count=271", "formula_digest='old'",
                           "audit_evidence=jsonb_set(audit_evidence,'{unresolved}','{\"pe\":\"missing\"}')"):
                cur.execute('SAVEPOINT bad')
                cur.execute('UPDATE payload SET '+change)
                assert not valid(),change
                cur.execute('ROLLBACK TO SAVEPOINT bad')
            cur.execute('UPDATE payload SET factor_values[1]=NULL,ready_mask=%s,ready_count=271,audit_evidence=%s',
                        ('0'+'1'*271,Json({'status':'ready','unresolved':{},'excluded':{FACTOR_SPECS[0].name:'insufficient_listing_history'}})))
            assert valid()  # A documented domain exclusion is not lost data.
    finally:
        conn.rollback();conn.close()


def test_group_valuation_ready_label_needs_both_groups_metrics_and_numerical_evidence():
    conn=get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('CREATE TEMP TABLE payload (snapshots jsonb)')
            groups = {
                code: {
                    'meta': {
                        'quality': {'status': 'computed'},
                        'publication': {
                            'publishable': True,
                            'certified_object': 'same_date_valid_sample_distribution',
                            'blockers': [],
                        },
                        'numerical_check': {
                            metric + '_count_median': 'passed'
                            for metric in ('pe', 'pe_ttm', 'pb', 'ps_ttm', 'dv_ttm')
                        },
                    },
                    'data': {'metrics': {
                        metric: {
                            'valid_count': 10, 'median': 1, 'population': 10,
                            'missing_codes': [], 'nonpositive_excluded_codes': [],
                            'missing_member_rows': [], 'invalid_field_codes': [],
                        }
                        for metric in ('pe', 'pe_ttm', 'pb', 'ps_ttm', 'dv_ttm')
                    }},
                }
                for code in ('000300.SH', '000688.SH')
            }
            cur.execute('INSERT INTO payload VALUES (%s)',(Json(groups),))
            def valid():
                cur.execute(sql.SQL('SELECT COALESCE(({}),false) FROM payload').format(business_predicate('valuation_percentile_snapshot')))
                return cur.fetchone()[0]
            assert valid()
            for expression in ("snapshots-'000688.SH'", "jsonb_set(snapshots,'{000300.SH,data,metrics,pe,median}','null')",
                               "jsonb_set(snapshots,'{000300.SH,data,metrics,pe,valid_count}','0')",
                               "jsonb_set(snapshots,'{000300.SH,meta,numerical_check}','{}')"):
                cur.execute('SAVEPOINT bad');cur.execute('UPDATE payload SET snapshots='+expression)
                assert not valid(),expression
                cur.execute('ROLLBACK TO SAVEPOINT bad')
    finally:
        conn.rollback();conn.close()


def test_technical_payload_checks_every_feature_and_evidenced_exclusion():
    from service.research.local_factors.ownership import TECHNICAL_FEATURES
    conn=get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('CREATE TEMP TABLE local_factor_current(trade_date date,ts_code text,technical_values jsonb,audit_evidence jsonb,factor_values float8[])')
            cur.execute('CREATE TEMP TABLE technical_factor_snapshot(snapshot_date date,ts_code text)')
            cur.execute("INSERT INTO technical_factor_snapshot VALUES ('2026-10-30','000001.SZ')")
            values={name:1 for name in TECHNICAL_FEATURES};values['adjustment_status']='applied'
            evidence={'technical_status':'ready','excluded':{}}
            cur.execute("INSERT INTO local_factor_current VALUES ('2026-10-30','000001.SZ',%s,%s,%s)",
                        (Json(values),Json(evidence),[1.0]*272))
            def valid():
                cur.execute(sql.SQL('SELECT COALESCE(({}),false) FROM technical_factor_snapshot').format(business_predicate('technical_factor_snapshot')))
                return cur.fetchone()[0]
            assert valid()
            for name in TECHNICAL_FEATURES:
                cur.execute('SAVEPOINT bad')
                cur.execute('UPDATE local_factor_current SET technical_values=technical_values-%s',(name,))
                assert not valid(),name
                cur.execute('ROLLBACK TO SAVEPOINT bad')
            values[TECHNICAL_FEATURES[0]]=None
            evidence['excluded'][TECHNICAL_FEATURES[0]]='insufficient_listing_history'
            cur.execute('UPDATE local_factor_current SET technical_values=%s,audit_evidence=%s',(Json(values),Json(evidence)))
            assert valid()
    finally:
        conn.rollback();conn.close()
