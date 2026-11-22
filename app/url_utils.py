"""Fetch an article from a URL and pull out its readable text.

Because the server downloads whatever URL a visitor types, we block addresses
that point at private/internal networks (SSRF protection).
"""
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3
TIMEOUT = 8
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FakeNewsDetector/1.0)"}


class ArticleError(Exception):
    """Problem the user can understand and fix (bad link, no article found...)."""


def _check_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ArticleError("Enter a full link that starts with http:// or https://")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 80, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ArticleError("That website could not be found. Check the link.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ArticleError("That link points to a private address, so it cannot be fetched.")


def _download(url: str) -> bytes:
    for _ in range(MAX_REDIRECTS + 1):
        _check_public_url(url)
        try:
            resp = requests.get(
                url, headers=HEADERS, timeout=TIMEOUT, stream=True, allow_redirects=False
            )
        except requests.RequestException:
            raise ArticleError("The page could not be loaded. Try pasting the text instead.")
        if resp.is_redirect or resp.is_permanent_redirect:
            url = urljoin(url, resp.headers.get("Location", ""))
            resp.close()
            continue
        if resp.status_code != 200:
            resp.close()
            raise ArticleError(
                f"The website answered with error {resp.status_code}. Try pasting the text instead."
            )
        body = resp.raw.read(MAX_BYTES + 1, decode_content=True)
        resp.close()
        if len(body) > MAX_BYTES:
            raise ArticleError("That page is too large to check.")
        return body
    raise ArticleError("That link redirects too many times.")


def extract_article(html: bytes) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
        tag.decompose()
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    body = "\n\n".join(p for p in paragraphs if len(p) >= 40)
    return title, body


def fetch_article(url: str) -> tuple[str, str]:
    """Return (title, article_text) or raise ArticleError."""
    title, body = extract_article(_download(url.strip()))
    if len(body) < 200:
        raise ArticleError("No article text was found on that page. Try pasting the text instead.")
    return title, body
