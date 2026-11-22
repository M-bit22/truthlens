"""TruthLens: Streamlit version.

Same model, same word explanations and same fact-check lookup as the FastAPI/Docker
version, but as a single Streamlit app that can be hosted free on Streamlit Community Cloud.
"""
import json
import re
from pathlib import Path

import streamlit as st

import ui_helpers as ui
from app import factcheck
from app.model import Detector, ModelNotReady
from app.url_utils import ArticleError, fetch_article

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "models" / "model.joblib"
METRICS_PATH = ROOT / "models" / "metrics.json"
MAX_CHARS, MIN_CHARS, PREVIEW_CHARS = 50_000, 20, 2_000

st.set_page_config(page_title="TruthLens", page_icon="✅", layout="centered")
st.markdown(ui.css_block(), unsafe_allow_html=True)


# ---------- loading ----------
@st.cache_resource(show_spinner="Loading the model…")
def load_detector():
    try:
        return Detector(MODEL_PATH)
    except ModelNotReady:
        return None


@st.cache_data
def load_metrics():
    if METRICS_PATH.exists():
        return json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    return None


def get_api_key():
    """Streamlit secret first (Community Cloud), then environment variable / .env (local)."""
    try:
        value = st.secrets.get("GOOGLE_FACTCHECK_API_KEY")
        if value:
            return str(value)
    except Exception:
        pass
    return factcheck.get_api_key()


def lookup_factchecks(text: str) -> dict:
    key = get_api_key()
    if not key:
        return {"state": "off"}
    try:
        result = factcheck.lookup(text[:MAX_CHARS], key)
    except factcheck.FactCheckUnavailable as err:
        return {"state": "error", "message": str(err)}
    return {"state": "ok", **result}


detector = load_detector()
metrics = load_metrics()

# ---------- session state ----------
for key, default in {"mode": "Paste text", "text_in": "", "url_in": "", "claim_in": "",
                     "result": None, "fc": None, "error": None, "pending": None}.items():
    st.session_state.setdefault(key, default)


def request_check():
    st.session_state.pending = "check"


def request_claim():
    st.session_state.pending = "claim"


def clear_all():
    st.session_state.update(text_in="", url_in="", claim_in="", result=None, fc=None, error=None, pending=None)


# ---------- actions (run before drawing, so the page always shows fresh results) ----------
def run_check():
    s = st.session_state
    s.error = None
    source = {"type": "text", "title": None}
    if s.mode == "Article link":
        url = s.url_in.strip()
        if not url:
            s.error = "Enter an article link first."
            return
        try:
            title, text = fetch_article(url)
        except ArticleError as err:
            s.error = str(err)
            return
        source = {"type": "url", "title": title or None}
    else:
        text = s.text_in.strip()
        if not text:
            s.error = "Paste some article text first."
            return
        if len(text) < MIN_CHARS:
            s.error = "Enter at least a full sentence to check."
            return
        if len(text) > MAX_CHARS:
            s.error = f"That text is too long. The limit is {MAX_CHARS:,} characters."
            return
    try:
        result = detector.predict(text)
    except ValueError as err:
        s.error = str(err)
        return
    result["source"] = source
    result["text_preview"] = text[:PREVIEW_CHARS]
    s.result = result
    s.fc = lookup_factchecks(source["title"] or text)


def run_claim():
    claim = st.session_state.claim_in.strip()
    st.session_state.fc = {"state": "short"} if len(claim) < 10 else lookup_factchecks(claim)


if detector is None:
    st.markdown(ui.nav_html(metrics, ready=False), unsafe_allow_html=True)
    st.error("The model file `models/model.joblib` was not found. Copy your trained model into the models folder and redeploy.")
    st.stop()

if st.session_state.pending == "check":
    with st.spinner("Checking the article…"):
        run_check()
elif st.session_state.pending == "claim":
    with st.spinner("Searching fact-check databases…"):
        run_claim()
st.session_state.pending = None

# ---------- page ----------
st.markdown(ui.nav_html(metrics, ready=True), unsafe_allow_html=True)
st.markdown(ui.HERO_HTML, unsafe_allow_html=True)

left, right = st.columns(2, gap="medium")

with left:
    with st.container(key="card_input"):
        st.radio("Input type", ["Paste text", "Article link"], key="mode", horizontal=True, label_visibility="collapsed")
        if st.session_state.mode == "Paste text":
            st.text_area("Article text", key="text_in", height=250, max_chars=MAX_CHARS,
                         placeholder="Paste a headline and the full article here. Longer text gives a more reliable result.")
            words = len(re.findall(r"\S+", st.session_state.text_in))
            st.caption(f"{words:,} word{'' if words == 1 else 's'}  ·  press Ctrl+Enter or click outside the box to update")
        else:
            st.text_input("Article link", key="url_in", placeholder="https://example.com/news/article")
            st.caption("The app downloads the page and reads its paragraphs. If a site blocks this, paste the text instead.")
        b1, b2, _ = st.columns([1.3, 1, 2])
        b1.button("Check article", type="primary", on_click=request_check)
        b2.button("Clear", on_click=clear_all)

with right:
    with st.container(key="card_result"):
        result = st.session_state.result
        if st.session_state.error:
            st.markdown(f'<div class="error">{ui.esc(st.session_state.error)}</div>', unsafe_allow_html=True)
        elif result is None:
            st.markdown('<div class="empty"><div class="h2">Nothing checked yet</div>'
                        "<p>Paste an article and choose <b>Check article</b>. Your result appears here.</p></div>",
                        unsafe_allow_html=True)
        else:
            st.markdown(ui.verdict_html(result), unsafe_allow_html=True)
            st.markdown(ui.gauge_html(result), unsafe_allow_html=True)
            st.markdown(f'<div>{ui.terms_html(result)}</div>', unsafe_allow_html=True)

with st.container(key="card_factcheck"):
    st.markdown('<div class="card-title">Published fact-checks</div>', unsafe_allow_html=True)
    with st.form("claim_form"):
        c1, c2 = st.columns([4, 1.3])
        c1.text_input("Search a specific claim", key="claim_in", label_visibility="collapsed",
                      placeholder="Or type a claim to look up, e.g. 5G towers spread coronavirus")
        c2.form_submit_button("Search claim", on_click=request_claim)
    st.markdown(f'<div>{ui.factcheck_html(st.session_state.fc)}</div>', unsafe_allow_html=True)

left2, right2 = st.columns(2, gap="medium")
with left2:
    with st.container(key="card_reading"):
        st.markdown('<div class="card-title">Your text with the key words marked</div>', unsafe_allow_html=True)
        st.markdown(ui.reading_html(result) if result else ui.READING_EMPTY, unsafe_allow_html=True)
        st.markdown(ui.LEGEND_HTML, unsafe_allow_html=True)
with right2:
    with st.container(key="dark_metrics"):
        st.markdown(ui.metrics_html(metrics), unsafe_allow_html=True)

st.markdown(ui.DISCLAIMER_HTML, unsafe_allow_html=True)
