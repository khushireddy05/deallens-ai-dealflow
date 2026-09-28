"""Fetch a company's own homepage for extra context.

The domain comes from untrusted pitch text, so this is a server-side request forgery (SSRF)
risk. Guards: HTTPS only, every host (and every redirect hop) must resolve to public
addresses, redirects are followed manually and capped, and the body size is capped.

Known limit: the hostname is resolved once to check it and again by the HTTP client to
connect, so a DNS-rebinding attacker could still race the two. Run this behind an egress
firewall if you handle hostile input.
"""

import ipaddress
import socket
import time
from collections.abc import Callable
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from ..normalize import normalize_domain
from .base import EnrichmentError

USER_AGENT = "deallens/0.1 (+company homepage lookup)"
MAX_EXCERPT_CHARS = 2000


def _default_resolver(host: str) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)]


def assert_public_host(
    host: str, resolver: Callable[[str], list[str]] = _default_resolver
) -> None:
    """Raise EnrichmentError unless `host` resolves only to public IP addresses."""
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(a.split("%")[0]) for a in resolver(host)]
        except (socket.gaierror, UnicodeError, OSError) as exc:
            raise EnrichmentError(f"DNS lookup failed for {host}") from exc
    if not addresses:
        raise EnrichmentError(f"DNS lookup returned nothing for {host}")
    for address in addresses:
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        if not address.is_global:
            raise EnrichmentError(f"Blocked non-public address for {host}")


class _PageParser(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self._text: list[str] = []
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag in self._SKIP:
            self._skip_depth += 1
        elif tag == "meta":
            name = (attributes.get("name") or attributes.get("property") or "").lower()
            if name in {"description", "og:description"} and not self.description:
                self.description = (attributes.get("content") or "").strip()

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip_depth and data.strip():
            self._text.append(data.strip())

    @property
    def text(self) -> str:
        return " ".join(" ".join(self._text).split())


def parse_page(html: str) -> dict:
    parser = _PageParser()
    parser.feed(html)
    return {
        "title": " ".join(parser.title.split()),
        "description": " ".join(parser.description.split()),
        "text_excerpt": parser.text[:MAX_EXCERPT_CHARS],
    }


class _Transient(Exception):
    pass


class WebsiteEnrichment:
    def __init__(
        self,
        timeout: float = 5.0,
        max_bytes: int = 500_000,
        max_redirects: int = 3,
        attempts: int = 2,
        resolver: Callable[[str], list[str]] = _default_resolver,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.attempts = max(1, attempts)
        self._resolver = resolver
        self._transport = transport
        self._sleep = sleep

    def enrich(self, domain: str) -> dict:
        host = normalize_domain(domain)
        if host is None:
            raise EnrichmentError(f"Not a valid domain: {domain!r}")
        url = f"https://{host}/"
        last_error = "unknown error"
        for attempt in range(1, self.attempts + 1):
            try:
                html, final_url = self._fetch(url)
            except _Transient as exc:
                last_error = str(exc)
                if attempt < self.attempts:
                    self._sleep(0.5 * 2 ** (attempt - 1))
                continue
            page = parse_page(html)
            if not any(page.values()):
                raise EnrichmentError("Page had no readable content")
            return {"domain": host, "url": final_url, **page}
        raise EnrichmentError(f"Website unreachable: {last_error}")

    def _fetch(self, url: str) -> tuple[str, str]:
        try:
            with httpx.Client(
                timeout=self.timeout,
                follow_redirects=False,
                transport=self._transport,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.5"},
            ) as client:
                for _ in range(self.max_redirects + 1):
                    parsed = urlparse(url)
                    if parsed.scheme != "https" or not parsed.hostname:
                        raise EnrichmentError("Blocked: only https:// URLs are fetched")
                    assert_public_host(parsed.hostname, self._resolver)
                    with client.stream("GET", url) as response:
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location:
                                raise EnrichmentError("Redirect without a location")
                            url = urljoin(url, location)
                            continue
                        if response.status_code >= 500:
                            raise _Transient(f"HTTP {response.status_code}")
                        if response.status_code >= 400:
                            raise EnrichmentError(f"HTTP {response.status_code}")
                        content_type = response.headers.get("content-type", "").lower()
                        if "html" not in content_type and "text" not in content_type:
                            raise EnrichmentError("Not an HTML page")
                        body = bytearray()
                        for chunk in response.iter_bytes():
                            body.extend(chunk)
                            if len(body) >= self.max_bytes:
                                break
                        text = bytes(body[: self.max_bytes]).decode(
                            response.encoding or "utf-8", errors="replace"
                        )
                        return text, url
                raise EnrichmentError("Too many redirects")
        except httpx.TimeoutException as exc:
            raise _Transient("timed out") from exc
        except httpx.TransportError as exc:
            raise _Transient(type(exc).__name__) from exc
