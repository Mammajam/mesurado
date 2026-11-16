"""Passage stage: split cleaned articles into citable passages (spec: content-pipeline R3.2 to R3.5).

A passage is about 150 to 300 words (a short one is allowed at the end of a section; at most 338 after merges), never crosses a heading, and
is an exact slice of the article text: passage["text"] == article_text[start:end]. Ids are
"<article id>#<three digit index>" in article order, so they stay the same while the article text is unchanged.

Algorithm, per section (the blocks between two headings):
  1. A paragraph longer than MAX_WORDS is cut on sentence boundaries into pieces of at most MAX_WORDS.
  2. Pieces are merged with the next piece while the passage so far has fewer than TARGET_MIN words and the
     merge stays within MAX_WORDS.
  3. A final piece with fewer than MIN_STANDALONE words is merged into the previous passage of the same
     section; if there is none it is dropped and counted (R3.5 reports articles that end up with no passage).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.stages.clean import CLEAN_DIR, Block, CleanArticle
from pipeline.stages.fetch import slug
from pipeline.text import split_sentences, word_count

TARGET_MIN = 150
MAX_WORDS = 300
MIN_STANDALONE = 20
HARD_MAX = MAX_WORDS + 2 * (MIN_STANDALONE - 1)  # one small prefix and one small tail may merge into a full passage
PASSAGES_DIR = CLEAN_DIR.parent / "passages"


@dataclass
class _Piece:
    start: int
    end: int
    words: int


def _pieces(block: Block) -> list[_Piece]:
    words = word_count(block.text)
    if words <= MAX_WORDS:
        return [_Piece(block.start, block.end, words)]
    # Cut into k roughly equal pieces (not 300 plus a tiny remainder) on sentence boundaries.
    k = -(-words // MAX_WORDS)
    target = words / k
    out: list[_Piece] = []
    cur: _Piece | None = None
    for s, e in split_sentences(block.text):
        w = word_count(block.text[s:e])
        if cur is not None and (cur.words + w > MAX_WORDS or (cur.words >= target and len(out) < k - 1)):
            out.append(cur)
            cur = None
        if cur is None:
            cur = _Piece(block.start + s, block.start + e, w)
        else:
            cur = _Piece(cur.start, block.start + e, cur.words + w)
    if cur is not None:
        out.append(cur)
    return out


def _section_passages(blocks: list[Block]) -> tuple[list[_Piece], int]:
    chunks: list[_Piece] = []
    cur: _Piece | None = None
    for b in blocks:
        for piece in _pieces(b):
            if cur is None:
                cur = piece
            elif (cur.words < TARGET_MIN and cur.words + piece.words <= MAX_WORDS) or cur.words < MIN_STANDALONE:
                cur = _Piece(cur.start, piece.end, cur.words + piece.words)
            else:
                chunks.append(cur)
                cur = piece
    if cur is not None:
        chunks.append(cur)
    dropped = 0
    if chunks and chunks[-1].words < MIN_STANDALONE:
        last = chunks.pop()
        if chunks:
            prev = chunks[-1]
            chunks[-1] = _Piece(prev.start, last.end, prev.words + last.words)
        else:
            dropped = 1
    return chunks, dropped


def split_article(art: CleanArticle) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return (passages, stats) for one cleaned article."""
    passages: list[dict[str, Any]] = []
    stack: list[tuple[int, str]] = []  # (level, heading text)
    section: list[Block] = []
    dropped = 0
    oversize = 0

    def flush() -> None:
        nonlocal dropped, oversize
        if not section:
            return
        chunks, d = _section_passages(section)
        dropped += d
        path = [t for _, t in stack]
        for c in chunks:
            if c.words > MAX_WORDS:
                oversize += 1  # a single sentence longer than the limit; kept whole
            passages.append({
                "id": f"{art.id}#{len(passages):03d}",
                "article": art.id,
                "heading_path": path,
                "text": art.text[c.start:c.end],
                "start": c.start,
                "end": c.end,
                "words": c.words,
            })
        section.clear()

    for b in art.blocks:
        if b.t == "h":
            flush()
            while stack and stack[-1][0] >= b.level:
                stack.pop()
            stack.append((b.level, b.text))
        else:
            section.append(b)
    flush()
    return passages, {"passages": len(passages), "dropped_short": dropped, "oversize": oversize}


def split_all(clean_dir: Path = CLEAN_DIR, out_dir: Path = PASSAGES_DIR, log=lambda s: None) -> tuple[list[dict[str, Any]], list[str]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    all_passages: list[dict[str, Any]] = []
    empty: list[str] = []
    for f in sorted(clean_dir.glob("*/*.json")):
        art = CleanArticle.from_json(json.loads(f.read_text(encoding="utf-8")))
        passages, stats = split_article(art)
        if not passages:
            empty.append(art.id)  # R3.5: report and drop the article from the pack
            log(f"{art.id}: NO PASSAGES")
            continue
        all_passages.extend(passages)
        log(f"{art.id}: {stats['passages']} passages")
    (out_dir / "passages.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in all_passages) + "\n", encoding="utf-8")
    return all_passages, empty


def main() -> int:
    from pipeline.stages.clean import clean_all

    clean_all()
    passages, empty = split_all()
    words = [p["words"] for p in passages]
    print(f"{len(passages)} passages; words min {min(words)}, median {sorted(words)[len(words) // 2]}, max {max(words)}; "
          f"{sum(1 for w in words if w < TARGET_MIN)} under {TARGET_MIN}; {len(empty)} articles without passages: {empty}")
    return 0 if not empty else 1


if __name__ == "__main__":
    sys.exit(main())
