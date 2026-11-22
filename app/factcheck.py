"""Look up published fact-checks for a claim (Google Fact Check Tools API).

The classifier only judges WRITING STYLE and only knows news up to ~2018. This
module adds a second, independent signal: has a professional fact-checker
(Snopes, PolitiFact, Reuters Fact Check...) already reviewed this claim?

The API key is read on the server only and is never sent to the browser.
Get a free key: https://console.cloud.google.com -> enable "Fact Check Tools API"
-> Credentials -> Create API key. Then put it in a `.env` file:
    GOOGLE_FACTCHECK_API_KEY=your-key-here
"""
import os
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
TIMEOUT = 8
MAX_QUERY_CHARS = 200
MAX_CLAIMS = 5


class FactCheckUnavailable(Exception):
    """The lookup could not run (network, quota, bad key). Message is user-safe."""


def _load_dotenv() -> None:
    """Tiny .env reader so Windows users don't need to set environment variables."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_api_key() -> str | None:
    _load_dotenv()
    return os.getenv("GOOGLE_FACTCHECK_API_KEY") or None


def build_query(text: str) -> str:
    """Fact-check search works best on one short claim: use the headline/first sentence."""
    text = re.sub(r"\s+", " ", text or "").strip()
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return first[:MAX_QUERY_CHARS].strip()


def parse_claims(payload: dict) -> list[dict]:
    """Flatten the API response into a small list the page can show."""
    out = []
    for claim in (payload.get("claims") or [])[:MAX_CLAIMS]:
        reviews = claim.get("claimReview") or []
        if not reviews:
            continue
        r = reviews[0]
        out.append({
            "claim": claim.get("text", ""),
            "claimant": claim.get("claimant", ""),
            "publisher": (r.get("publisher") or {}).get("name", "Unknown publisher"),
            "rating": r.get("textualRating", ""),
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "date": (r.get("reviewDate") or claim.get("claimDate") or "")[:10],
        })
    return out


STOPWORDS = set("""a an the and or but if of to in on at by for with from as is are was were be been being has have had
do does did not no this that these those it its they them their he she his her we you your our i about after before
over under into than then so such will would can could should may might also just more most very said says say
viral claim claims social media posts post video image images circulating shared share fact check checked debunked
false true news article report reports according new""".split())


def keyword_query(text: str, limit: int = 7) -> str:
    """Fallback: the first few meaningful words of the opening sentence (keeps amounts like \u20b91,000)."""
    words = re.findall(r"[\u20b9$\u20ac\u00a3]?\d[\d,.]*[A-Za-z]*|[A-Za-z][A-Za-z'-]+", build_query(text))
    seen, picked = set(), []
    for w in words:
        k = w.lower()
        if k in STOPWORDS or k in seen or (len(k) < 3 and not k[0].isdigit()):
            continue
        seen.add(k)
        picked.append(w.rstrip(",."))
        if len(picked) >= limit:
            break
    return " ".join(picked)


def shorten(text: str, max_chars: int = 90) -> str:
    text = build_query(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0].strip()


def build_queries(text: str) -> list[str]:
    """Several searches, most specific first. Long sentences often match nothing."""
    out = []
    for q in (build_query(text), shorten(text), keyword_query(text)):
        q = q.strip()
        if len(q) >= 10 and q.lower() not in [x.lower() for x in out]:
            out.append(q)
    return out


def _search(query: str, api_key: str) -> list[dict]:
    try:
        res = requests.get(
            ENDPOINT,
            params={"query": query, "key": api_key, "languageCode": "en", "pageSize": MAX_CLAIMS},
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        raise FactCheckUnavailable("Could not reach the fact-check service. Try again later.")
    if res.status_code in (400, 403):
        raise FactCheckUnavailable("The fact-check API key was rejected. Check the key and that the API is enabled.")
    if res.status_code == 429:
        raise FactCheckUnavailable("The fact-check service is rate limited right now. Try again later.")
    if not res.ok:
        raise FactCheckUnavailable("The fact-check service had a problem. Try again later.")
    return parse_claims(res.json())


def lookup(text: str, api_key: str) -> dict:
    queries = build_queries(text)
    for q in queries:
        claims = _search(q, api_key)
        if claims:
            return {"query": q, "tried": queries, "claims": claims}
    return {"query": queries[0] if queries else "", "tried": queries, "claims": []}
