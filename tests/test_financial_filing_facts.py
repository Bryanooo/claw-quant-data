from datetime import date
from decimal import Decimal

import pytest

from service.financial_filing_facts import recover_rows, prepare_facts


def fact(**changes):
    return dict(dict(fact_id=1, statement_table='balancesheet', ts_code='300750.SZ',
                end_date=date(2025,12,31), published_on=date(2026,3,10),
                available_on=date(2026,3,11), field_name='fix_assets', value_yuan=Decimal(100),
                revoked_at=None), **changes)


def recover(rows=(), facts=None, cutoff=date(2026,10,8)):
    return recover_rows(list(rows), [fact()] if facts is None else facts,
                        table='balancesheet', fields=['fix_assets','total_assets'], cutoff=cutoff)


def test_only_proven_fields_are_recovered_without_backdating_whole_rows():
    rows, evidence = recover()
    assert rows[0]['fix_assets']==100
    assert rows[0]['total_assets'] is None
    assert evidence[0]['fact_ids']==[1]
    assert evidence[0]['status']=='recovered_from_original'
    assert recover(cutoff=date(2026,3,10)) == ([], [])
    assert recover(cutoff=date(2026,3,9)) == ([], [])
    assert recover(facts=[fact(revoked_at='2026-11-03')]) == ([], [])


def test_conflicting_fact_does_not_silently_override_supplier():
    row=dict(ts_code='300750.SZ',end_date=date(2025,12,31),ann_date=date(2026,3,10),fix_assets=99)
    result, evidence=recover([row])
    assert result[0]['fix_assets'] is None
    assert row['fix_assets']==99
    assert evidence[0]['status']=='conflicting_fact_blocked'
    assert recover(facts=[fact(),fact(fact_id=2,value_yuan=101)])[0][0]['fix_assets'] is None


def test_publication_versions_and_parent_scope_are_not_mixed():
    row=dict(ts_code='300750.SZ',end_date=date(2025,12,31),ann_date=date(2026,4,1),fix_assets=None)
    result,evidence=recover([row])
    assert result[0]['fix_assets'] is None
    assert evidence[0]['status']=='different_version_not_merged'
    row['fix_assets']=80
    row['ann_date']=date(2026,2,1)
    newer = recover([row])[0][0]
    assert newer['fix_assets'] == 100
    assert newer['total_assets'] is None  # no older vendor field is carried across versions
    assert newer['ann_date'] == date(2026,3,10)
    row.update(ann_date=date(2026,3,10),fix_assets=None,report_type=4)
    assert recover([row])[0][0]['fix_assets'] is None


def test_duplicate_vendor_identity_and_nonfinite_fact_fail_closed():
    row=dict(ts_code='300750.SZ',end_date=date(2025,12,31),ann_date=date(2026,3,10))
    with pytest.raises(ValueError): recover([row,row])
    with pytest.raises(ValueError): recover(facts=[fact(value_yuan='NaN')])


def test_no_total_to_component_alias_and_no_cross_version_fill():
    assert recover(facts=[fact(field_name='fix_assets_total')])==( [], [] )
    rows,_=recover(facts=[fact(), fact(fact_id=2,field_name='total_assets',value_yuan=200,
                                   published_on=date(2026,4,1),available_on=date(2026,4,2))])
    assert rows[0]['total_assets']==200
    assert rows[0]['fix_assets'] is None


def test_projecting_one_field_cannot_resurrect_an_older_filing():
    newer = fact(fact_id=2, field_name='total_assets', value_yuan=200,
                 published_on=date(2026,4,1), available_on=date(2026,4,2))
    rows, evidence = recover_rows([], [fact(), newer], table='balancesheet',
                                  fields=['fix_assets'], cutoff=date(2026,10,8))
    assert rows == []
    assert evidence[0]['status'] == 'latest_version_field_unproven'
    assert evidence[0]['fact_ids'] == [2]
    row = dict(ts_code='300750.SZ', end_date=date(2025,12,31), ann_date=date(2026,3,10), fix_assets=100)
    rows, evidence = recover_rows([row], [fact(), newer], table='balancesheet',
                                  fields=['fix_assets'], cutoff=date(2026,10,8))
    assert rows == []  # latest version proves no projected field; no stale vendor row
    assert row['fix_assets'] == 100
    # The invalidation must not depend on an older proof being present too.
    rows, evidence = recover_rows([row], [newer], table='balancesheet',
                                  fields=['fix_assets'], cutoff=date(2026,10,8))
    assert rows == []
    assert evidence[-1]['status'] == 'latest_version_field_unproven'
    # Before the later publication becomes available the original is usable.
    rows, _ = recover_rows([], [fact(), newer], table='balancesheet',
                          fields=['fix_assets'], cutoff=date(2026,4,1))
    assert rows[0]['fix_assets'] == 100


def test_newer_proof_replaces_only_known_fields_and_leaves_no_stale_vendor_values():
    old = dict(ts_code='300750.SZ',end_date=date(2025,12,31),ann_date=date(2026,2,1),
               _disclosure=date(2026,2,1),fix_assets=80,total_assets=900,report_type=1)
    rows, evidence = recover([old])
    assert rows[0]['fix_assets'] == 100
    assert rows[0]['total_assets'] is None
    assert '_disclosure' not in rows[0]
    assert old['fix_assets'] == 80 and old['total_assets'] == 900
    assert evidence[0]['status'] == 'older_version_replaced_by_proven_fields'
    assert evidence[1]['status'] == 'recovered_from_original'


def test_preparation_imports_only_current_column_and_checks_review_contract():
    row=dict(field='fixed_assets_net_in_note',page=2,label='固定资产',unit='人民币千元',
             current='100',comparative='80')
    doc=dict(artifact_id=1,sha256='a'*64,symbol='300750.SZ',period='2025-12-31',published_on='2026-03-10',
             scope='consolidated',review='reviewed units, dates and consolidated scope',unit='人民币千元',
             rows=[{k:row[k] for k in ('field','page','label')}],extracted_facts=[row],
             url='https://example.invalid/report.pdf',title='Annual report')
    output=prepare_facts([doc],reviewer='reviewer')
    assert len(output)==1 and output[0]['value_yuan']==100  # extractor already normalized
    assert output[0]['end_date']==date(2025,12,31)
    with pytest.raises(ValueError): prepare_facts([dict(doc,scope='parent')],reviewer='reviewer')
    with pytest.raises(ValueError): prepare_facts([doc],reviewer='')
    with pytest.raises(ValueError): prepare_facts([dict(doc,extracted_facts=[])],reviewer='reviewer')
