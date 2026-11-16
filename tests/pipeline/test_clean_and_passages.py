"""Tests for the clean and passage stages (spec: content-pipeline R3; tasks 4.1 to 4.4).

Includes a real Wikipedia page (fixtures/lake_piso.json) and property-based tests for the splitter:
passage text is an exact slice, passages never cross a heading, size bounds hold, ids are stable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.stages.clean import Block, CleanArticle, clean_html
from pipeline.stages.passages import HARD_MAX, MAX_WORDS, MIN_STANDALONE, TARGET_MIN, split_article
from pipeline.text import normalize_text, split_sentences, word_count

META = {"id": "wp:Test", "title": "Test", "subject": "history", "revision": "1"}
FIXTURES = Path(__file__).parent / "fixtures"


def page(body: str) -> str:
    return f'<div class="mw-content-ltr mw-parser-output">{body}</div>'


def clean(body: str) -> CleanArticle:
    return clean_html(page(body), META)


# ---- cleaning: snippets ----------------------------------------------------------------------


def test_citations_notes_and_pronunciation_are_removed():
    art = clean(
        '<p>Monrovia<sup class="reference"><a>[a]</a></sup> (<span class="IPA">/mon/</span>; <span>French</span>) is a city.'
        '<sup class="reference">[1]</sup> It lies on the coast.<sup class="noprint Inline-Template">[citation needed]</sup></p>'
    )
    assert art.text == "Monrovia (French) is a city. It lies on the coast."
    art = clean('<p>Founded<sup class="reference">[2]</sup> (<span class="IPA">/x/</span>) in 1822.</p>')
    assert art.text == "Founded in 1822."  # empty brackets left by removed items are cleaned up


def test_heading_stack_and_skipped_sections():
    art = clean(
        '<p>Lead text here.</p>'
        '<div class="mw-heading mw-heading2"><h2>History</h2></div><p>History text.</p>'
        '<div class="mw-heading mw-heading3"><h3>Early period</h3></div><p>Early text.</p>'
        '<div class="mw-heading mw-heading2"><h2>References</h2></div><ol class="references"><li>ref</li></ol>'
        '<div class="mw-heading mw-heading3"><h3>Cited works</h3></div><p>Smith 2001.</p>'
        '<div class="mw-heading mw-heading2"><h2>Geography</h2></div><p>Geography text.</p>'
        '<div class="mw-heading mw-heading2"><h2>External links</h2></div><ul><li>site</li></ul>'
    )
    kinds = [(b.t, b.level, b.text) for b in art.blocks]
    assert kinds == [
        ("p", 0, "Lead text here."), ("h", 2, "History"), ("p", 0, "History text."), ("h", 3, "Early period"),
        ("p", 0, "Early text."), ("h", 2, "Geography"), ("p", 0, "Geography text."),
    ]
    assert art.stats["skipped_sections"] == 2  # References (with its subsection) and External links


def test_boxes_tables_figures_and_hatnotes_are_dropped():
    art = clean(
        '<div class="hatnote">For other uses, see X.</div><table class="infobox"><tr><td>Population 5</td></tr></table>'
        '<p>Real text.</p><figure><figcaption>A caption</figcaption></figure>'
        '<div class="navbox"><table><tr><td>Navigation</td></tr></table></div>'
        '<table class="wikitable"><tr><td>cell</td></tr></table><p>More text. <span class="interlanguage-link">[fr]</span></p>'
    )
    assert art.text == "Real text.\n\nMore text."
    assert art.stats["dropped_tables"] >= 2


def test_lists_nested_lists_and_bibliography_lines():
    art = clean(
        '<ul><li>Alpha <ul><li>Beta nested</li></ul></li><li>Gamma</li></ul>'
        '<ul><li><cite class="citation book">Smith, J. (2000). A Book.</cite></li><li>Jones (1999). ISBN 0-123-45678-9</li></ul>'
    )
    assert [b.text for b in art.blocks] == ["Alpha", "Beta nested", "Gamma"]
    assert art.stats["dropped_citations"] == 2


def test_empty_heading_is_removed_and_text_is_normalized():
    art = clean('<div class="mw-heading mw-heading2"><h2>Empty</h2></div><div class="mw-heading mw-heading2"><h2>Full</h2></div><p>Café  ́ text</p>')
    assert [b.text for b in art.blocks if b.t == "h"] == ["Full"]
    assert " " not in art.text


@settings(max_examples=60, deadline=None)
@given(st.lists(st.text(alphabet="abc de.,", min_size=1, max_size=40).map(str.strip).filter(bool), min_size=1, max_size=8))
def test_block_offsets_always_slice_the_text(paragraphs):
    art = clean("".join(f"<p>{p}</p>" for p in paragraphs))
    for b in art.blocks:
        assert art.text[b.start:b.end] == b.text
    assert [b.start for b in art.blocks] == sorted(b.start for b in art.blocks)


# ---- cleaning: a real page -------------------------------------------------------------------


def test_real_page_is_clean():
    d = json.loads((FIXTURES / "lake_piso.json").read_text(encoding="utf-8"))
    art = clean_html(d["html"], d)
    assert art.stats["words"] > 200
    assert not re.search(r"\[\d+\]|\[[a-z]\]", art.text), "citation or footnote markers left in the text"
    assert "Retrieved" not in art.text and "ISBN" not in art.text and "encarta" not in art.text.lower()
    heads = {b.text.casefold() for b in art.blocks if b.t == "h"}
    assert not heads & {"references", "external links", "see also"}


# ---- sentences -------------------------------------------------------------------------------


def test_sentence_splitting_handles_abbreviations_and_initials():
    text = "Dr. Smith met J. J. Roberts in St. Paul. He left at 3.5 p.m. The end."
    spans = split_sentences(text)
    parts = [text[s:e] for s, e in spans]
    assert parts == ["Dr. Smith met J. J. Roberts in St. Paul.", "He left at 3.5 p.m.", "The end."]


@settings(max_examples=100, deadline=None)
@given(st.lists(st.lists(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=6, max_size=12), min_size=1, max_size=5).map(" ".join), min_size=1, max_size=10))
def test_sentence_spans_are_ordered_clean_slices(parts):
    text = " ".join(p.capitalize() + "." for p in parts)
    spans = split_sentences(text)
    assert [text[s:e] for s, e in spans] == [p.capitalize() + "." for p in parts]
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))


def test_normalize_text():
    assert normalize_text("A  b ( ; ) ,c") == "A b,c"


# ---- passages --------------------------------------------------------------------------------


def make_article(sections: list[tuple[int, str, list[str]]], lead: list[str] | None = None) -> CleanArticle:
    """sections: (heading level, heading text, paragraphs). Returns a CleanArticle with exact offsets."""
    blocks: list[Block] = [Block("p", p) for p in (lead or [])]
    for level, title, paras in sections:
        blocks.append(Block("h", title, level))
        blocks += [Block("p", p) for p in paras]
    pos = 0
    parts = []
    for b in blocks:
        b.start, b.end = pos, pos + len(b.text)
        parts.append(b.text)
        pos = b.end + 2
    return CleanArticle("wp:Test", "Test", "history", "1", "\n\n".join(parts), blocks)


def para(n_words: int, seed: str = "w") -> str:
    """A paragraph of n words made of 10-word sentences."""
    words = [f"{seed}{i % 7}" for i in range(n_words)]
    sents = [" ".join(words[i:i + 10]).capitalize() + "." for i in range(0, n_words, 10)]
    return " ".join(sents)


def test_long_paragraph_is_cut_on_sentence_boundaries():
    art = make_article([], lead=[para(700)])
    passages, _ = split_article(art)
    assert len(passages) >= 3
    assert all(p["words"] <= MAX_WORDS for p in passages)
    assert all(p["text"].endswith(".") and p["text"][0].isupper() for p in passages)


def test_passages_follow_headings_and_ids_are_stable():
    art = make_article([(2, "History", [para(100), para(100)]), (3, "Early", [para(160)]), (2, "Geography", [para(60)])], lead=[para(50)])
    a, _ = split_article(art)
    b, _ = split_article(art)
    assert [p["id"] for p in a] == [p["id"] for p in b] == [f"wp:Test#{i:03d}" for i in range(len(a))]
    paths = [p["heading_path"] for p in a]
    assert paths == [[], ["History"], ["History", "Early"], ["Geography"]]


def test_tiny_tail_merges_and_tiny_section_is_dropped():
    art = make_article([(2, "A", [para(200), "Short tail here."]), (2, "B", ["Too short."])])
    passages, stats = split_article(art)
    assert len(passages) == 1 and "Short tail here." in passages[0]["text"]
    assert stats["dropped_short"] == 1


def test_article_without_content_has_no_passages():
    assert split_article(make_article([], lead=["Tiny."]))[0] == []


SECTION = st.tuples(st.sampled_from([2, 3]), st.text(alphabet="ABCDE ", min_size=1, max_size=8).map(str.strip).filter(bool),
                    st.lists(st.integers(5, 400), min_size=1, max_size=5))


@settings(max_examples=80, deadline=None)
@given(st.lists(SECTION, min_size=1, max_size=6), st.lists(st.integers(5, 400), max_size=3))
def test_passage_invariants(sections, lead_sizes):
    art = make_article([(lv, t, [para(n, f"s{i}x") for n in sizes]) for i, (lv, t, sizes) in enumerate(sections)],
                       lead=[para(n, "lead") for n in lead_sizes])
    passages, _ = split_article(art)
    heading_spans = [(b.start, b.end) for b in art.blocks if b.t == "h"]
    prev_end = -1
    for p in passages:
        assert art.text[p["start"]:p["end"]] == p["text"]  # exact slice (validator rule)
        assert p["start"] >= prev_end  # ordered, no overlap
        prev_end = p["end"]
        assert MIN_STANDALONE <= p["words"] <= HARD_MAX
        assert p["words"] == word_count(p["text"])
        assert not any(p["start"] < he and hs < p["end"] for hs, he in heading_spans)  # never crosses a heading
    # Only words in sections with fewer than MIN_STANDALONE words (they carry nothing citable) may be lost.
    kept = sum(p["words"] for p in passages)
    total = sum(word_count(b.text) for b in art.blocks if b.t != "h")
    assert kept <= total
    assert total - kept < MIN_STANDALONE * (len(sections) + 1)
    assert [p["id"] for p in passages] == [f"wp:Test#{i:03d}" for i in range(len(passages))]


def test_target_constants_match_the_spec():
    assert (TARGET_MIN, MAX_WORDS) == (150, 300)
