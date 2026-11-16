"""Clean stage: Wikipedia HTML to plain article text with a block structure (spec: content-pipeline R3.1, R3.5).

Output per article (pipeline/work/clean/<subject>/<slug>.json):
  text    the article as plain text, blocks separated by one blank line
  blocks  [{"t": "h"|"p"|"li", "level": int (headings), "start": int, "end": int}] offsets into text

Headings are kept as blocks (so the reader can render them and passages can carry a heading path) but
are never part of a passage. Tables, infoboxes, navigation boxes, figures, references and
"See also" style sections are dropped in v1, and counted in the stats.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from pipeline.stages.fetch import WORK_DIR as FETCH_DIR
from pipeline.stages.fetch import slug
from pipeline.text import normalize_text, word_count

CLEAN_DIR = FETCH_DIR.parent / "clean"

# Whole sections that are not learning content. Matched on the lower-cased heading text.
SKIP_SECTIONS = {
    "references", "notes", "footnotes", "citations", "sources", "bibliography", "external links",
    "further reading", "see also", "works cited", "gallery", "explanatory notes", "general references",
    "cited sources", "notes and references",
}
# Elements removed before any text is read.
DROP_SELECTORS = [
    "style", "script", "link", "meta", "figure", "table", "sup.reference", "sup.noprint", "sup.Inline-Template",
    "span.mw-editsection", "span.IPA", "span.noexcerpt", "span.mwe-math-element", "div.hatnote", "div.navbox",
    "div.navbox-styles", "div.shortdescription", "div.sistersitebox", "div.side-box", "div.portalbox", "div.noprint",
    "div.thumb", "div.gallery", "ul.gallery", "div.toc", "div#toc", "div.reflist", "div.refbegin", "ol.references",
    "div.mw-references-wrap", "div.metadata", "div.ambox", "div.sidebar", "div.infobox", "div.authority-control",
    "span.Z3988", "div.mw-empty-elt", "p.mw-empty-elt", "span.mw-empty-elt", "div.printfooter", "div.catlinks",
    "div.dablink", "div.rellink", "div.mw-authority-control",
    "span.interlanguage-link", "span.noprint", "span.geo-inline", "span.geo-default", "span.geo", "span.geo-dms", "span.geo-nondefault",
]
_BIBLIOGRAPHY = re.compile(r"\bISBN\b|\bISSN\b|Archived from the original|\bdoi:\s*10\.", re.I)
LIST_TAGS = {"ul", "ol", "dl"}
CONTAINER_TAGS = {"div", "section", "blockquote"}


@dataclass
class Block:
    t: str  # "h", "p" or "li"
    text: str
    level: int = 0
    start: int = 0
    end: int = 0


@dataclass
class CleanArticle:
    id: str
    title: str
    subject: str
    revision: str
    text: str
    blocks: list[Block]
    stats: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "subject": self.subject, "revision": self.revision,
            "text": self.text,
            "blocks": [{"t": b.t, "level": b.level, "start": b.start, "end": b.end} for b in self.blocks],
            "stats": self.stats,
        }

    @staticmethod
    def from_json(d: dict[str, Any]) -> "CleanArticle":
        return CleanArticle(
            d["id"], d["title"], d["subject"], d["revision"], d["text"],
            [Block(b["t"], d["text"][b["start"]:b["end"]], b["level"], b["start"], b["end"]) for b in d["blocks"]],
            d.get("stats", {}),
        )


def _own_text(el: Tag) -> str:
    """Text of an element without text from nested lists (those become their own blocks)."""
    clone = BeautifulSoup(str(el), "html.parser")
    for nested in clone.find_all(list(LIST_TAGS)):
        nested.decompose()
    for br in clone.find_all("br"):
        br.replace_with(" ")
    return normalize_text(clone.get_text())


def _heading_level(div: Tag) -> int:
    for c in div.get("class", []):
        if c.startswith("mw-heading") and c[len("mw-heading"):].isdigit():
            return int(c[len("mw-heading"):])
    h = div.find(["h2", "h3", "h4", "h5", "h6"])
    return int(h.name[1]) if h else 2


def clean_html(html: str, meta: dict[str, Any]) -> CleanArticle:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("div.mw-parser-output") or soup
    stats = {"dropped_tables": len(root.select("table")), "skipped_sections": 0, "dropped_citations": 0}
    for sel in DROP_SELECTORS:
        for el in root.select(sel):
            el.decompose()
    blocks: list[Block] = []
    skip_level: int | None = None  # while set, we are inside a skipped section of this heading level

    def emit(t: str, text: str, level: int = 0) -> None:
        if not text:
            return
        if t != "h" and _BIBLIOGRAPHY.search(text):
            stats["dropped_citations"] += 1  # a bibliography line that was not marked up as a citation
            return
        blocks.append(Block(t, text, level))

    def walk(parent: Tag) -> None:
        nonlocal skip_level
        for el in parent.children:
            if not isinstance(el, Tag):
                continue
            classes = el.get("class", [])
            if el.name == "div" and any(c.startswith("mw-heading") for c in classes):
                level = _heading_level(el)
                h = el.find(["h1", "h2", "h3", "h4", "h5", "h6"])
                title = normalize_text(h.get_text()) if h else ""
                if skip_level is not None and level > skip_level:
                    continue
                skip_level = None
                if title.casefold() in SKIP_SECTIONS:
                    skip_level = level
                    stats["skipped_sections"] += 1
                    continue
                emit("h", title, level)
            elif skip_level is not None:
                continue
            elif el.name == "p":
                if el.select_one("cite.citation"):
                    stats["dropped_citations"] += 1
                else:
                    emit("p", _own_text(el))
            elif el.name in LIST_TAGS:
                for li in el.find_all(["li", "dt", "dd"]):
                    if li.select_one("cite.citation"):
                        stats["dropped_citations"] += 1
                    else:
                        emit("li", _own_text(li))
            elif el.name in CONTAINER_TAGS:
                if el.name == "blockquote" and not el.find(["p", "div", "ul", "ol"]):
                    emit("p", _own_text(el))
                else:
                    walk(el)
            elif el.name in {"h2", "h3", "h4"}:  # headings outside the usual wrapper
                level = int(el.name[1])
                title = normalize_text(el.get_text())
                if skip_level is not None and level > skip_level:
                    continue
                skip_level = level if title.casefold() in SKIP_SECTIONS else None
                if skip_level is None:
                    emit("h", title, level)

    walk(root)

    # Remove headings that have no content before the next heading of the same or higher level.
    cleaned: list[Block] = []
    for i, b in enumerate(blocks):
        if b.t == "h":
            has_content = False
            for x in blocks[i + 1:]:
                if x.t == "h" and x.level <= b.level:
                    break
                if x.t != "h":
                    has_content = True
                    break
            if not has_content:
                continue
        cleaned.append(b)

    parts: list[str] = []
    pos = 0
    for b in cleaned:
        b.start = pos
        b.end = pos + len(b.text)
        parts.append(b.text)
        pos = b.end + 2  # blank line between blocks
    text = "\n\n".join(parts)
    stats["blocks"] = len(cleaned)
    stats["words"] = sum(word_count(b.text) for b in cleaned if b.t != "h")
    return CleanArticle(meta["id"], meta["title"], meta["subject"], str(meta["revision"]), text, cleaned, stats)


def clean_all(fetch_dir: Path = FETCH_DIR, out_dir: Path = CLEAN_DIR, log=lambda s: None) -> list[CleanArticle]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*/*.json"):
        old.unlink()  # never leave output from an earlier selection behind
    result: list[CleanArticle] = []
    current = {i["id"] for i in json.loads((fetch_dir / "items.json").read_text(encoding="utf-8"))["items"]}
    for f in sorted(fetch_dir.glob("*/*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d["id"] not in current:
            continue  # left over from an earlier selection
        art = clean_html(d["html"], d)
        sdir = out_dir / art.subject
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / f"{slug(art.id)}.json").write_text(json.dumps(art.to_json(), ensure_ascii=False), encoding="utf-8")
        result.append(art)
        log(f"{art.id}: {art.stats['words']} words, {art.stats['blocks']} blocks")
    return result


def main() -> int:
    arts = clean_all(log=print)
    empty = [a.id for a in arts if a.stats["words"] == 0]
    print(f"cleaned {len(arts)} articles; {len(empty)} with no text: {empty}")
    return 0 if not empty else 1


if __name__ == "__main__":
    sys.exit(main())
