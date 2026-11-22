"""Text cleaning shared by training and prediction.

Training and the API MUST use the same function, otherwise the model sees
different text at prediction time than it saw during training.
"""
import re

_PIC_TWITTER = re.compile(r"pic\.twitter\.com/\S+", re.I)
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_HTML = re.compile(r"<[^>]+>")
_HANDLE = re.compile(r"[@#]\w+")
# "WASHINGTON (Reuters) - " style datelines at the start of an article
_DATELINE = re.compile(r"^\s*[A-Z][A-Za-z.,'/ -]{1,40}\(Reuters\)\s*[-\u2013\u2014]?\s*")
# Source "signatures" that identify the publisher instead of the writing style.
# Left in, a model can reach ~99% accuracy just by spotting the word "reuters".
_SOURCE_TELLS = re.compile(
    r"\b(reuters|getty images?|featured image|image via|21st century wire|via)\b", re.I
)
_NON_LETTERS = re.compile(r"[^a-z\s]")
_SPACES = re.compile(r"\s+")


def clean_text(text: str) -> str:
    text = text or ""
    text = _DATELINE.sub("", text)
    text = _PIC_TWITTER.sub(" ", text)
    text = _URL.sub(" ", text)
    text = _HTML.sub(" ", text)
    text = _HANDLE.sub(" ", text)
    text = _SOURCE_TELLS.sub(" ", text)
    text = text.lower()
    text = _NON_LETTERS.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))
