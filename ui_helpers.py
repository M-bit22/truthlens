"""Pure helpers that build the HTML for the Streamlit page (no Streamlit import, easy to test).

Rules that keep Streamlit's markdown from mangling the HTML:
  * every HTML string starts with a block tag (<div ...>)
  * no blank lines and no leading indentation inside the string
  * "$" is escaped, because Streamlit would treat $...$ as maths
"""
import base64
import html
import math
import re

# ---------- escaping ----------
def esc(text) -> str:
    return html.escape(str(text or "")).replace("$", "&#36;")


def esc_multiline(text: str) -> str:
    return esc(text).replace("\r\n", "\n").replace("\n", "<br>")


# ---------- verdict copy (same wording as the web version) ----------
def verdict_copy(d: dict) -> dict:
    p = d["fake_probability"]
    pct = lambda x: round(x * 100)
    table = {
        "fake": ("Likely fake", "The writing looks much more like fake news than like real reporting.", pct(p), "chance this is fake"),
        "real": ("Likely real", "The writing looks much more like real reporting than like fake news.", pct(1 - p), "chance this is real"),
        "uncertain": ("Too close to call", "The writing has traits of both real and fake news, so the model cannot lean either way.", pct(p), "chance this is fake"),
    }
    title, sub, number, caption = table[d["verdict"]]
    return {"title": title, "sub": sub, "number": number, "caption": caption}


def verdict_html(d: dict) -> str:
    c = verdict_copy(d)
    return f'<div class="verdict is-{d["verdict"]}"><div class="h2">{esc(c["title"])}</div><p>{esc(c["sub"])}</p></div>'


def terms_html(d: dict) -> str:
    def chips(terms, cls, empty):
        if not terms:
            return f'<p class="none">{empty}</p>'
        return '<div class="chips">' + "".join(f'<span class="chip {cls}">{esc(t["term"])}</span>' for t in terms) + "</div>"

    notice = ""
    if d.get("short_text"):
        notice = (f'<p class="notice">This text is only {int(d["word_count"])} words. Short text makes the result '
                  "less reliable. Paste the full article if you can.</p>")
    return (
        notice
        + '<div class="terms-title">Words that pushed it toward fake</div>'
        + chips(d["top_fake_terms"], "fake", "No strong fake-leaning words found.")
        + '<div class="terms-title">Words that pushed it toward real</div>'
        + chips(d["top_real_terms"], "real", "No strong real-leaning words found.")
    )


# ---------- gauge (an SVG shown as an image, which works in every Streamlit version) ----------
CX, CY, R, SW = 150, 150, 120, 26


def _pt(p: float, r: float = R):
    a = math.pi * (1 - p)
    return CX + r * math.cos(a), CY - r * math.sin(a)


def _arc(p1: float, p2: float) -> str:
    x1, y1 = _pt(p1)
    x2, y2 = _pt(p2)
    return f"M{x1:.2f} {y1:.2f} A{R} {R} 0 0 1 {x2:.2f} {y2:.2f}"


def gauge_svg(d: dict) -> str:
    c = verdict_copy(d)
    p = d["fake_probability"]
    mx, my = _pt(min(0.97, max(0.03, p)))
    f = "Space Grotesk, Inter, Segoe UI, Arial, sans-serif"
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 178">'
        f'<path d="{_arc(0, 0.4)}" fill="none" stroke="#cde8df" stroke-width="{SW}"/>'
        f'<path d="{_arc(0.4, 0.6)}" fill="none" stroke="#f1e1bd" stroke-width="{SW}"/>'
        f'<path d="{_arc(0.6, 1)}" fill="none" stroke="#c0235c" stroke-width="{SW}"/>'
        f'<circle cx="{mx:.2f}" cy="{my:.2f}" r="11" fill="#ffffff" stroke="#12172b" stroke-width="4"/>'
        f'<text x="150" y="126" text-anchor="middle" font-family="{f}" font-weight="600" font-size="54" fill="#12172b">{c["number"]}%</text>'
        f'<text x="150" y="148" text-anchor="middle" font-family="{f}" font-size="13" fill="#6b7185">{html.escape(c["caption"])}</text>'
        f'<text x="20" y="172" font-family="{f}" font-size="13" fill="#6b7185">Real</text>'
        f'<text x="280" y="172" text-anchor="end" font-family="{f}" font-size="13" fill="#6b7185">Fake</text>'
        "</svg>"
    )


def gauge_html(d: dict) -> str:
    c = verdict_copy(d)
    b64 = base64.b64encode(gauge_svg(d).encode("utf-8")).decode("ascii")
    alt = html.escape(f"{c['number']} percent {c['caption']}", quote=True)
    return f'<div class="gauge"><img src="data:image/svg+xml;base64,{b64}" alt="{alt}"/></div>'


# ---------- highlighted text ----------
def highlight(text: str, fake_terms, real_terms) -> str:
    mapping = {}
    for t in fake_terms:
        mapping[t["term"]] = "fake"
    for t in real_terms:
        mapping[t["term"]] = "real"
    out, last = [], 0
    for m in re.finditer(r"[A-Za-z]{2,}", text):      # same word shape the model's tokenizer sees
        cls = mapping.get(m.group(0).lower())
        if not cls:
            continue
        out.append(esc_multiline(text[last:m.start()]))
        out.append(f'<mark class="{cls}">{esc(m.group(0))}</mark>')
        last = m.end()
    out.append(esc_multiline(text[last:]))
    return "".join(out)


def reading_html(d: dict) -> str:
    src = ""
    if d["source"]["type"] == "url":
        title = (esc(d["source"]["title"]) + ". ") if d["source"].get("title") else ""
        src = f'<p class="source-title">{title}Showing the start of the text found at the link.</p>'
    body = highlight(d["text_preview"], d["top_fake_terms"], d["top_real_terms"])
    return f'<div class="reading">{src}{body}</div>'


LEGEND_HTML = '<div class="legend"><mark class="fake">word</mark> pushes toward fake <mark class="real">word</mark> pushes toward real</div>'
READING_EMPTY = '<div class="reading"><p class="placeholder">The words that influenced the result will be highlighted here.</p></div>'


# ---------- fact-check results ----------
_BAD = re.compile(r"(not true|isn'?t true|untrue|false|fake|pants|incorrect|misleading|fabricat|hoax|no evidence|scam|nothing to do|no link|not related|baseless|debunk|unproven)")
_GOOD = re.compile(r"^(mostly |largely )?(true|correct|accurate)\b")


def rating_class(rating: str) -> str:
    x = (rating or "").lower().strip()
    if not x:
        return ""
    if _BAD.search(x):
        return "bad"
    if _GOOD.match(x):
        return "good"
    return ""


def rating_parts(rating: str):
    text = (rating or "Reviewed").strip()
    return ("Reviewed", text) if len(text) > 28 else (text, "")


def factcheck_html(fc) -> str:
    if not fc:
        return '<div class="fc-note">After you check an article, this looks for claims already reviewed by professional fact-checkers.</div>'
    state = fc.get("state")
    if state == "off":
        return ('<div class="fc-note">Fact-check lookup is switched off.</div><div class="fc-setup">To turn it on, add your free Google key '
                "as the secret <code>GOOGLE_FACTCHECK_API_KEY</code> in the app settings.</div>")
    if state == "error":
        return f'<div class="fc-note">{esc(fc.get("message", "Fact-check lookup failed."))}</div>'
    if state == "short":
        return '<div class="fc-note">Type a claim of at least a few words.</div>'
    claims = fc.get("claims", [])
    tried = fc.get("tried") or [fc.get("query", "")]
    searched = f'<div class="fc-query">Searched for: {esc("  ·  ".join(t for t in tried if t))}</div>'
    if not claims:
        return ('<div class="fc-note">No published fact-check matched this article\'s main claim. That does not mean it is true: '
                "it may simply be too new or too small to have been reviewed.</div>" + searched +
                '<div class="fc-note" style="margin-top:.6rem">Tip: type the core claim in the box above, in plain words, to search it directly.</div>')
    items = []
    for c in claims:
        cls = rating_class(c.get("rating"))
        pill, long = rating_parts(c.get("rating"))
        meta = esc(c.get("publisher", "")) + (" · " + esc(c["date"]) if c.get("date") else "")
        label = esc(c.get("title") or c.get("claim") or "Read the fact-check")
        url = c.get("url", "")
        link = f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{label}</a>' if re.match(r"^https?://", url or "") else label
        verdict = f'<div class="fc-verdict {cls}">{esc(long)}</div>' if long else ""
        claim = ""
        if c.get("claim"):
            who = f' ({esc(c["claimant"])})' if c.get("claimant") else ""
            claim = f'<div class="fc-claim">Claim: {esc(c["claim"])}{who}</div>'
        items.append(f'<div class="fc-item"><div class="fc-top"><span class="fc-rating {cls}">{esc(pill)}</span><span class="fc-pub">{meta}</span></div>{link}{verdict}{claim}</div>')
    return '<div class="fc-list">' + "".join(items) + "</div>" + searched


# ---------- header + metrics ----------
def nav_html(metrics: dict | None, ready: bool) -> str:
    if ready and metrics:
        served = next((r for r in metrics["results"] if r["model"] == metrics["served_model"]), metrics["results"][0])
        text, dot = f"Model ready. {served['accuracy'] * 100:.1f}% on 2015–2018 news", "ok"
    elif ready:
        text, dot = "Model ready", "ok"
    else:
        text, dot = "Model not trained yet", "bad"
    return ('<div class="nav"><div class="brand"><span class="logo">✓</span><span>TruthLens</span></div>'
            f'<div class="status"><span class="dot {dot}"></span>{esc(text)}</div></div>')


HERO_HTML = ('<div class="hero"><div class="h1">Paste an article. See how it reads.</div>'
             "<p>The model compares the writing with thousands of real and fake news stories, then shows the words behind its decision.</p></div>")

DISCLAIMER_HTML = ('<div class="disclaimer">This tool spots writing patterns that are common in fake news. It does not check facts. '
                   "For anything important, confirm the claims with a source you trust. The model was trained on news from 2015 to 2018, "
                   "so recent events may not be judged reliably.</div>")


def metrics_html(metrics: dict | None) -> str:
    head = '<div class="card-title light">How well it was tested</div>'
    if not metrics:
        return f'<div class="dark">{head}<p class="hint-dark">No test results found. Add models/metrics.json to show them here.</p></div>'
    served = next((r for r in metrics["results"] if r["model"] == metrics["served_model"]), metrics["results"][0])
    rows = "".join(f'<div class="row"><span>{esc(r["model"])}</span><b>{r["accuracy"] * 100:.1f}%</b></div>' for r in metrics["results"])
    return (f'<div class="dark">{head}<div class="big"><strong>{served["accuracy"] * 100:.1f}%</strong>'
            f'<span>accuracy on {int(metrics["test_articles"]):,} articles the model had never seen</span></div>'
            f'<p class="hint-dark">Training data covers news from 2015 to 2018 only.</p><div class="rows">{rows}</div></div>')


# ---------- styling ----------
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap');
:root{--ink:#12172b;--muted:#6b7185;--line:#e6e8ef;--field:#f6f7fb;--accent:#4338ff;--fake:#c0235c;--fake-tint:#fbe3ec;--real:#1f7a52;--real-tint:#dcf0e5;--unsure:#9a6a12}
.stApp{background:#f3f4f8;font-family:'Inter',system-ui,sans-serif}
header[data-testid="stHeader"]{background:transparent}
footer{visibility:hidden}
.block-container{max-width:1020px;padding-top:1.6rem;padding-bottom:3rem}
div[class*="st-key-card_"]{background:#fff;border:1px solid #eceef5;border-radius:22px;padding:1.3rem 1.4rem}
div[class*="st-key-card_"] [data-testid="stVerticalBlock"]{gap:.7rem}
div[class*="st-key-dark_"]{background:#12172b;border-radius:22px;padding:1.3rem 1.4rem}
.nav{display:flex;align-items:center;justify-content:space-between;gap:1rem;margin-bottom:2rem}
.brand{display:flex;align-items:center;gap:.65rem;font:600 15px 'Space Grotesk',sans-serif;color:var(--ink)}
.logo{display:inline-grid;place-items:center;width:26px;height:26px;border-radius:8px;background:var(--ink);color:#fff;font-size:15px}
.status{display:inline-flex;align-items:center;gap:.5rem;padding:.35rem .85rem;background:#fff;border:1px solid var(--line);border-radius:999px;font-size:12px;color:var(--muted)}
.dot{width:7px;height:7px;border-radius:50%;background:#b7bcc9;display:inline-block}.dot.ok{background:#14935f}.dot.bad{background:var(--fake)}
.hero .h1{font:700 clamp(2.1rem,5vw,3rem)/1.08 'Space Grotesk',sans-serif;letter-spacing:-.02em;color:var(--ink);max-width:13em;margin-bottom:1rem}
.hero p{color:var(--muted);max-width:34em;font-size:1.02rem;margin:0 0 1.6rem}
.gauge img{display:block;width:100%;max-width:310px;margin:.6rem auto}
.verdict .h2{font:700 1.9rem/1.1 'Space Grotesk',sans-serif;color:var(--fake);margin-bottom:.35rem}
.verdict.is-real .h2{color:var(--real)}.verdict.is-uncertain .h2{color:var(--unsure)}
.verdict p{margin:0;color:var(--muted);font-size:13.5px}
.empty .h2{font:700 1.6rem/1.1 'Space Grotesk',sans-serif;color:var(--ink);margin-bottom:.35rem}.empty p{color:var(--muted);margin:0}
.terms-title{font:600 12.5px 'Inter',sans-serif;color:var(--ink);margin:1rem 0 .55rem}
.chips{display:flex;flex-wrap:wrap;gap:.45rem}
.chip{font-size:12.5px;padding:.28rem .8rem;border-radius:999px}.chip.fake{background:var(--fake-tint);color:#8d1745}.chip.real{background:var(--real-tint);color:#17603f}
.none{margin:0;font-size:13px;color:var(--muted)}
.notice{margin:.6rem 0 0;padding:.6rem .8rem;background:#fdf3dc;color:#7a520c;border-radius:12px;font-size:13px}
.error{padding:.8rem 1rem;background:var(--fake-tint);color:#8d1745;border-radius:12px;margin:0}
.card-title{font:600 1.1rem 'Space Grotesk',sans-serif;color:var(--ink);margin:0}.card-title.light{color:#fff;margin-bottom:1rem}
.reading{background:var(--field);border:1px solid var(--line);border-radius:14px;padding:1rem;line-height:1.85;max-height:340px;overflow:auto;overflow-wrap:anywhere;color:var(--ink);font-size:15px}
.reading .placeholder{margin:0;color:var(--muted)}
mark{border-radius:6px;padding:.05em .3em;font-weight:500}
mark.fake{background:var(--fake-tint);color:#8d1745;box-shadow:inset 0 -2px 0 var(--fake)}
mark.real{background:var(--real-tint);color:#17603f;box-shadow:inset 0 -2px 0 var(--real)}
.legend{font-size:12px;color:var(--muted);display:flex;gap:.9rem;flex-wrap:wrap;align-items:center}
.source-title{font-size:12.5px;color:var(--muted);margin:0 0 .6rem}
.fc-note{color:var(--muted);font-size:13.5px}.fc-query{margin-top:.9rem;font-size:12px;color:var(--muted)}
.fc-list{display:grid;gap:.75rem}
.fc-item{border:1px solid var(--line);border-radius:14px;padding:.9rem 1rem;background:var(--field);font-size:14px;color:var(--ink)}
.fc-top{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem .75rem;margin-bottom:.35rem}
.fc-rating{font:600 12px 'Inter',sans-serif;padding:.22rem .7rem;border-radius:999px;background:#eceef5;color:var(--ink)}
.fc-rating.bad{background:var(--fake-tint);color:#8d1745}.fc-rating.good{background:var(--real-tint);color:#17603f}
.fc-pub{font-size:12.5px;color:var(--muted)}
.fc-item a{color:var(--accent);font-weight:600;text-decoration:none}.fc-item a:hover{text-decoration:underline}
.fc-verdict{margin-top:.35rem;font-size:13.5px}.fc-verdict.bad{color:#8d1745}.fc-verdict.good{color:#17603f}
.fc-claim{margin-top:.25rem;font-size:13.5px;color:var(--muted)}
.fc-setup{margin-top:.6rem;padding:.8rem 1rem;background:#fdf3dc;color:#7a520c;border-radius:12px;font-size:13px}
.fc-setup code{background:rgba(0,0,0,.06);padding:.05em .35em;border-radius:5px}
.dark{color:#fff}.dark .big{display:flex;align-items:center;gap:.9rem;margin-bottom:.6rem}
.dark .big strong{font:600 3.2rem/1 'Space Grotesk',sans-serif;letter-spacing:-.02em}
.dark .big span{font-size:12px;color:#aab0c5;max-width:12em;line-height:1.35}
.hint-dark{color:#aab0c5;font-size:13px;margin:0 0 1rem}
.dark .row{display:flex;justify-content:space-between;padding:.7rem 0;border-top:1px solid rgba(255,255,255,.09);font-size:13.5px}
.disclaimer{margin-top:1.4rem;font-size:12.5px;color:var(--muted);max-width:52em}
.stButton>button,.stFormSubmitButton>button{border-radius:999px;font-weight:600;padding:.45rem 1.3rem}
[data-testid="stForm"]{border:none;padding:0}
"""


def css_block() -> str:
    # blank lines would end Streamlit's HTML block, so drop them
    body = "\n".join(line for line in CSS.splitlines() if line.strip())
    return f"<style>\n{body}\n</style>"
