

def test_transport_count_is_unknown_for_absent_malformed_or_conflicting_response_counts():
    from service.data_coverage.transport import transport_manifest
    def manifest(status, **fields):
        event = dict(request_key='a', completion_status=status, completion_evidence={'verified': True}, **fields)
        return transport_manifest([event], [{'request_key':'a'}])
    assert manifest('complete')['rows_fetched'] is None
    assert manifest('complete', rows_fetched=False)['rows_fetched'] is None
    assert manifest('complete', rows_fetched='invalid')['rows_fetched'] is None
    assert manifest('complete', rows_fetched=-1)['rows_fetched'] is None
    assert manifest('empty')['rows_fetched'] == 0
    assert manifest('complete', rows_fetched='9')['rows_fetched'] == 9
    assert not manifest('empty', rows_fetched=9)['verified']
