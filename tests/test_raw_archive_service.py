from service.data_service.raw_archive import RawArchiveService


class Contract:
    api_name = "daily"
    title = "日线行情"
    collectable = True
    implementation = {"mode": "specialized"}
    document_ids = (27,)


class Catalog:
    def list(self):
        return (Contract(),)

    def get(self, api_name):
        if api_name != "daily":
            from service.tushare_catalog import InterfaceNotFoundError

            raise InterfaceNotFoundError(api_name)
        return Contract()


class Repository:
    def interface_stats(self, api_names):
        assert api_names == ["daily"]
        return [
            {
                "api_name": "daily",
                "request_count": 3,
                "successful_requests": 2,
                "empty_requests": 1,
                "failed_requests": 0,
                "latest_request_at": None,
                "has_records": True,
            }
        ]

    def requests(self, api_name, **_query):
        return ([{"request_id": 3, "api_name": api_name}], 1)

    def records(self, api_name, **_query):
        return ([{"api_name": api_name, "record_hash": "a" * 64}], None)

    def coverage(self, api_name):
        return {"api_name": api_name, "record_count": 100}


def test_raw_archive_service_exposes_layer_status_and_document_links():
    service = RawArchiveService(Repository(), Catalog())

    interface = service.list_interfaces()[0]
    coverage = service.coverage("daily")

    assert interface["implementation_mode"] == "specialized"
    assert interface["request_count"] == 3
    assert interface["has_records"] is True
    assert coverage["record_count"] == 100
    assert coverage["document_urls"] == [
        "https://tushare.pro/document/2?doc_id=27"
    ]


def test_raw_record_paging_does_not_force_an_expensive_total():
    service = RawArchiveService(Repository(), Catalog())

    result = service.list_records(
        "daily",
        request_hash=None,
        record_hash=None,
        start_time=None,
        end_time=None,
        limit=100,
        offset=0,
        include_total=False,
    )

    assert result["page"]["total"] is None
    assert result["data"][0]["record_hash"] == "a" * 64
