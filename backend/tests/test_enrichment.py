import httpx
import pytest

from app.enrichment.base import EnrichmentError
from app.enrichment.website import WebsiteEnrichment, assert_public_host, parse_page

PUBLIC_IP = "93.184.216.34"


def public_resolver(host):
    return [PUBLIC_IP]


def enricher(handler, **kwargs):
    kwargs.setdefault("resolver", public_resolver)
    kwargs.setdefault("sleep", lambda s: None)
    return WebsiteEnrichment(transport=httpx.MockTransport(handler), **kwargs)


HTML = """<html><head><title> Acme  Robots </title>
<meta name="description" content="We build warehouse robots">
<style>body {color: red}</style><script>var secret = 1;</script></head>
<body><h1>Acme</h1><p>Robots for   warehouses.</p></body></html>"""


def ok_page(request):
    return httpx.Response(200, text=HTML, headers={"content-type": "text/html; charset=utf-8"})


# ---------- SSRF guard ----------


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::1", "0.0.0.0", "::ffff:127.0.0.1"],
)
def test_private_literal_addresses_are_blocked(host):
    with pytest.raises(EnrichmentError, match="Blocked"):
        assert_public_host(host)


def test_hostname_resolving_to_private_address_is_blocked():
    with pytest.raises(EnrichmentError, match="Blocked"):
        assert_public_host("internal.example", lambda h: ["10.1.2.3"])


def test_hostname_with_any_private_address_is_blocked():
    with pytest.raises(EnrichmentError, match="Blocked"):
        assert_public_host("mixed.example", lambda h: [PUBLIC_IP, "127.0.0.1"])


def test_public_address_is_allowed():
    assert_public_host("fine.example", public_resolver)
    assert_public_host(PUBLIC_IP)


def test_dns_failure_is_an_enrichment_error():
    def failing(host):
        raise OSError("no such host")

    with pytest.raises(EnrichmentError, match="DNS"):
        assert_public_host("nope.example", failing)


# ---------- fetching ----------


def test_fetches_and_parses_homepage():
    info = enricher(ok_page).enrich("https://www.Acme.example/about")
    assert info["domain"] == "acme.example"
    assert info["url"] == "https://acme.example/"
    assert info["title"] == "Acme Robots"
    assert info["description"] == "We build warehouse robots"
    assert "Robots for warehouses." in info["text_excerpt"]
    assert "secret" not in info["text_excerpt"]
    assert "color: red" not in info["text_excerpt"]


def test_rejects_invalid_domain():
    with pytest.raises(EnrichmentError, match="valid domain"):
        enricher(ok_page).enrich("not a domain")


def test_redirect_to_private_host_is_blocked():
    def handler(request):
        if request.url.host == "acme.example":
            return httpx.Response(302, headers={"location": "https://evil.example/"})
        return ok_page(request)

    def resolver(host):
        return ["10.0.0.1"] if host == "evil.example" else [PUBLIC_IP]

    with pytest.raises(EnrichmentError, match="Blocked"):
        enricher(handler, resolver=resolver).enrich("acme.example")


def test_redirect_to_http_is_blocked():
    def handler(request):
        return httpx.Response(302, headers={"location": "http://acme.example/"})

    with pytest.raises(EnrichmentError, match="only https"):
        enricher(handler).enrich("acme.example")


def test_redirect_loop_is_capped():
    def handler(request):
        return httpx.Response(302, headers={"location": "https://acme.example/again"})

    with pytest.raises(EnrichmentError, match="Too many redirects"):
        enricher(handler).enrich("acme.example")


def test_follows_a_safe_redirect():
    def handler(request):
        if request.url.path == "/":
            return httpx.Response(301, headers={"location": "/home"})
        return ok_page(request)

    info = enricher(handler).enrich("acme.example")
    assert info["url"] == "https://acme.example/home"


def test_client_error_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404)

    with pytest.raises(EnrichmentError, match="HTTP 404"):
        enricher(handler).enrich("acme.example")
    assert len(calls) == 1


def test_server_error_is_retried_then_reported():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(EnrichmentError, match="unreachable"):
        enricher(handler, attempts=3).enrich("acme.example")
    assert len(calls) == 3


def test_transient_error_then_success():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectTimeout("slow")
        return ok_page(request)

    assert enricher(handler).enrich("acme.example")["title"] == "Acme Robots"
    assert len(calls) == 2


def test_non_html_is_rejected():
    def handler(request):
        return httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})

    with pytest.raises(EnrichmentError, match="Not an HTML"):
        enricher(handler).enrich("acme.example")


def test_response_size_is_capped():
    big = "<html><body>" + ("word " * 200_000) + "</body></html>"

    def handler(request):
        return httpx.Response(200, text=big, headers={"content-type": "text/html"})

    info = enricher(handler, max_bytes=10_000).enrich("acme.example")
    assert len(info["text_excerpt"]) <= 2000


def test_empty_page_is_an_error():
    def handler(request):
        return httpx.Response(200, text="<html></html>", headers={"content-type": "text/html"})

    with pytest.raises(EnrichmentError, match="no readable content"):
        enricher(handler).enrich("acme.example")


def test_parse_page_handles_og_description():
    page = parse_page('<meta property="og:description" content="Hello there"><p>x</p>')
    assert page["description"] == "Hello there"
