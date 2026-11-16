"""Small text helpers shared by the clean and passages stages (spec: content-pipeline R3)."""

from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+")
# Left behind when pronunciations, footnote markers or dates inside brackets are removed.
_EMPTY_PARENS = re.compile(r"\(\s*[;,:\-–]?\s*\)|\[\s*\]")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?)])")
_SPACE_AFTER_OPEN = re.compile(r"([(\[])\s+")
_LEADING_SEPARATOR = re.compile(r"([(\[])\s*[;,:]\s*")  # "(; French)" left by a removed pronunciation


def normalize_text(text: str) -> str:
    """NFC, no-break spaces to spaces, whitespace collapsed, empty brackets and stray spaces removed."""
    text = unicodedata.normalize("NFC", text).replace("\xa0", " ").replace("​", "")
    text = _WS.sub(" ", text).strip()
    for _ in range(2):  # a removed item can leave "( ; )" that only becomes empty after one pass
        text = _EMPTY_PARENS.sub("", text)
        text = _WS.sub(" ", text).strip()
    text = _LEADING_SEPARATOR.sub(r"\1", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = _SPACE_AFTER_OPEN.sub(r"\1", text)
    return text


def word_count(text: str) -> int:
    return len(text.split())


_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "mt", "gen", "col", "capt", "lt", "sgt", "rev", "hon",
    "vs", "etc", "no", "nos", "inc", "co", "ltd", "fig", "ca", "approx", "dept", "gov", "pres", "sen", "rep",
    "ft", "cf", "ed", "eds", "vol", "pp", "esp", "ie", "eg", "al",
}
_BOUNDARY = re.compile(r"""([.!?])(["')\]]*)(\s+)(?=["'(\[]?[A-Z0-9])""")


def split_sentences(text: str) -> list[tuple[int, int]]:
    """Return (start, end) offsets of sentences in text.

    Spans never include the whitespace between sentences, so text[start:end] is always a clean
    sentence. Abbreviations and single-letter initials do not end a sentence.
    """
    spans: list[tuple[int, int]] = []
    start = 0
    for m in _BOUNDARY.finditer(text):
        end = m.start(3)  # sentence ends right after the closing punctuation
        if m.group(1) == ".":
            before = text[start:m.start(1)]
            last = re.findall(r"[A-Za-z]+\.?$|\d+$", before.rstrip(".")) if before else []
            raw = (last[-1] if last else "").rstrip(".")
            token = raw.lower()
            dotted = re.search(r"\b(?:e\.g|i\.e)$", before.rstrip("."), re.I) is not None
            initial = len(raw) == 1 and raw.isupper()  # "J. J. Roberts"; lower-case "p.m." can end a sentence
            if token in _ABBREVIATIONS or initial or dotted:
                continue
        if end > start:
            spans.append((start, end))
        start = m.end()
    if start < len(text.rstrip()):
        spans.append((start, len(text.rstrip())))
    return spans
