import pytest

from scripts.archive_financial_filing import validate_url, fetch


@pytest.mark.parametrize('url',[
    'http://static.cninfo.com.cn/finalpage/2026-04-16/123.PDF',
    'https://static.cninfo.com.cn.evil/finalpage/2026-04-16/123.PDF',
    'https://u:p@static.cninfo.com.cn/finalpage/2026-04-16/123.PDF',
    'https://static.cninfo.com.cn/finalpage/2026-04-16/123.PDF?q=1',
    'https://static.cninfo.com.cn/finalpage/2026-99-16/123.PDF',
])
def test_filing_url_fails_closed(url):
    with pytest.raises(ValueError): validate_url(url)


def test_bounded_original_fetch_never_follows_redirect_or_accepts_html():
    url = 'https://static.cninfo.com.cn/finalpage/2026-04-16/123.PDF'
    class Response:
        status_code = 200
        headers = {}
        body = b'%PDF-1.4 test'
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def iter_content(self,*args): yield self.body
    response = Response()
    calls = []
    def get(url,**kw):
        calls.append(kw)
        return response
    assert fetch(url,http_get=get)[0] == response.body
    assert calls[0]['allow_redirects'] is False
    response.status_code = 302
    with pytest.raises(ValueError,match='no retry'): fetch(url,http_get=get)
    response.status_code = 200
    response.body = b'<html>blocked</html>'
    with pytest.raises(ValueError,match='not a PDF'): fetch(url,http_get=get)
    response.body = b'%PDF-'+b'a'*(20*1024*1024)
    with pytest.raises(ValueError,match='budget'): fetch(url,http_get=get)
