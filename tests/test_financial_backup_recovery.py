from io import StringIO

import pytest

from scripts.audit_financial_backup import financial_copy_rows
from scripts import recover_financial_backup


def test_financial_backup_parser_is_data_only_and_preserves_nulls():
    text = 'SET statement_timeout = 0;\nCOPY public.income (ts_code, end_date, revenue) FROM stdin;\nA\t2025-12-31\t\\N\n\\.\n'
    assert list(financial_copy_rows(StringIO(text),'income')) == [
        dict(ts_code='A',end_date='2025-12-31',revenue=None)]


@pytest.mark.parametrize('text',[
    'COPY public.evil (ts_code, end_date) FROM stdin;\n\\.\n',
    'COPY public.income (ts_code, end_date) FROM stdin;\nA\t2025-12-31\n',
    'COPY public.income (ts_code, end_date) FROM stdin;\nA\n\\.\n',
    'COPY public.income (ts_code, end_date) FROM stdin;\nA\\tB\t2025-12-31\n\\.\n',
    'COPY public.income (ts_code, ts_code, end_date) FROM stdin;\n\\.\n',
])
def test_financial_backup_parser_rejects_ambiguous_or_truncated_streams(text):
    with pytest.raises(ValueError):
        list(financial_copy_rows(StringIO(text),'income'))


def test_archive_verification_requires_matching_digest_identity_and_root(tmp_path, monkeypatch):
    import hashlib
    monkeypatch.setattr(recover_financial_backup,'__file__',str(tmp_path/'scripts'/'recover.py'))
    root = tmp_path/'backups'
    root.mkdir()
    path = root/'claw-quant-20261031-221129.dump'
    path.write_bytes(b'archive')
    digest = hashlib.sha256(b'archive').hexdigest()
    sidecar = root/(path.name+'.sha256')
    sidecar.write_text(f'{digest}  {path.name}\n')
    assert recover_financial_backup.verify_backup(path)[1] == digest
    path.write_bytes(b'changed')
    with pytest.raises(ValueError,match='checksum mismatch'):
        recover_financial_backup.verify_backup(path)
    sidecar.write_text(f'{digest} wrong.dump\n')
    with pytest.raises(ValueError,match='identity mismatch'):
        recover_financial_backup.verify_backup(path)
