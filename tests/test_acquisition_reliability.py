from requests import HTTPError, Response

from service.acquisition_runtime.reliability import classify_failure


def test_http_429_is_classified_as_rate_limited_not_network():
    response = Response()
    response.status_code = 429
    error = HTTPError(
        "429 Client Error: Too Many Requests",
        response=response,
    )

    assert classify_failure(error) == "rate_limited"


def test_other_http_transport_error_remains_network():
    response = Response()
    response.status_code = 502
    error = HTTPError("502 Server Error", response=response)

    assert classify_failure(error) == "network"
