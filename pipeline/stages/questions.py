"""Sample-question stage: rule-based example questions linked to passages (spec: content-pipeline R9).

No generative model is used. Questions come from two rules:
  lead     "Who was X?" / "What is X?" for the opening passage of an article, chosen from the first sentence
  heading  a template per well-known section heading ("What is the history of X?") linked to the first passage
           under that heading
A question is kept only if its linked passage is in the top RETRIEVAL_RANK results of the keyword search, so every
example shown to a student can actually be answered by the pack. Selection per subject is deterministic and spread
over articles (largest articles first, one question per article before a second).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from pipeline.stages.index import bm25_search, load_keyword_index

PER_SUBJECT = 20
RETRIEVAL_RANK = 5
HEADING_SHARE = 6  # section questions reserved per subject, so the examples are not all What-is-X
HEADING_TEMPLATES = {
    "history": "What is the history of {t}?",
    "early life": "What was the early life of {t}?",
    "geography": "What is the geography of {t} like?",
    "climate": "What is the climate of {t}?",
    "economy": "What is the economy of {t} like?",
    "demographics": "Who lives in {t}?",
    "etymology": "Where does the name {t} come from?",
    "government": "How is {t} governed?",
    "politics": "How does politics work in {t}?",
    "education": "What is education like in {t}?",
    "culture": "What is the culture of {t}?",
    "religion": "What religions are found in {t}?",
    "languages": "Which languages are spoken in {t}?",
    "transport": "How do people travel in {t}?",
    "transportation": "How do people travel in {t}?",
}
_PAREN = re.compile(r"\([^()]*\)")
_DEFINITION = re.compile(r"^(?P<subject>[^,;:]{1,80}?)\s+(?P<verb>is|was|are|were)\s+(?P<rest>(?:an?|the|one)\b.*)$", re.S)
# Words in the class noun phrase ("was the 20th president of Liberia") that mark a person.
_PERSON_WORDS = re.compile(
    r"\b(president|politician|activist|statesman|stateswoman|lawyer|general|king|queen|emperor|mansa|ruler|businessman|"
    r"businesswoman|soldier|leader|abolitionist|writer|pastor|explorer|minister|diplomat|economist|journalist|educator|"
    r"governor|missionary|nobel|rebel|warlord|dictator|poet|musician|footballer|scholar)\b", re.I)


def lead_question(title: str, first_sentence: str) -> str | None:
    """'Who was X?' for a person, 'What is/was X?' for other things; None if the sentence is not a plain definition.

    Parentheses (dates, pronunciations) are removed first. The sentence must start with the subject and
    its verb ("Lake Piso is a coastal lagoon"), so "Politics of Liberia takes place in..." produces no question.
    """
    plain = re.sub(r"\s+", " ", _PAREN.sub("", first_sentence)).strip()
    m = _DEFINITION.match(plain)
    if not m or len(m.group("subject").split()) > len(title.split()) + 4:
        return None
    verb = m.group("verb")
    noun_phrase = re.split(r"\b(?:of|that|which|who|in|during|between|for|to|with|at)\b", m.group("rest"), maxsplit=1)[0]
    if _PERSON_WORDS.search(noun_phrase):
        return f"Who {'was' if verb in ('was', 'were') else 'is'} {title}?"
    return f"What {verb} {title}?"


def _first_sentence(text: str) -> str:
    from pipeline.text import split_sentences

    spans = split_sentences(text)
    return text[spans[0][0]:spans[0][1]] if spans else text


def candidates(passages: list[dict], items: list[dict]) -> list[dict[str, Any]]:
    by_article: dict[str, list[dict]] = {}
    for p in passages:
        by_article.setdefault(p["article"], []).append(p)
    out: list[dict[str, Any]] = []
    for item in items:
        ps = by_article.get(item["id"], [])
        if not ps:
            continue
        base = {"subject": item["subject"], "article": item["id"], "size": len(ps)}
        lead = next((p for p in ps if not p["heading_path"]), None)
        q = lead_question(item["title"], _first_sentence(lead["text"])) if lead else None
        if q:
            out.append({**base, "question": q, "passage": lead["id"], "kind": "lead", "rank": 0})
        seen: set[str] = set()
        for p in ps:
            key = p["heading_path"][0].casefold() if p["heading_path"] else ""
            if key in HEADING_TEMPLATES and key not in seen:
                seen.add(key)
                out.append({**base, "question": HEADING_TEMPLATES[key].format(t=item["title"]), "passage": p["id"],
                            "kind": "heading", "rank": 1})
    return out


def build_sample_questions(passages: list[dict], items: list[dict], keyword_index: dict | None = None,
                           per_subject: int = PER_SUBJECT) -> list[dict[str, Any]]:
    cands = candidates(passages, items)
    if keyword_index is not None:
        cands = [c for c in cands
                 if c["passage"] in [pid for pid, _ in bm25_search(keyword_index, c["question"], RETRIEVAL_RANK)]]
    chosen: list[dict[str, Any]] = []
    for subject in sorted({c["subject"] for c in cands}):
        pool = [c for c in cands if c["subject"] == subject]
        leads = sorted((c for c in pool if c["kind"] == "lead"), key=lambda c: (-c["size"], c["article"]))
        heads = sorted((c for c in pool if c["kind"] == "heading"), key=lambda c: (-c["size"], c["article"], c["passage"]))
        picked: list[dict[str, Any]] = []
        used: dict[str, int] = {}

        def take(source: list[dict[str, Any]], limit: int, per_article: int) -> None:
            for c in source:
                if len(picked) >= limit:
                    return
                if c not in picked and used.get(c["article"], 0) < per_article:
                    picked.append(c)
                    used[c["article"]] = used.get(c["article"], 0) + 1

        take(leads, per_subject - HEADING_SHARE, 1)  # mostly "what/who is X", then section questions, then fill up
        take(heads, per_subject, 1)
        take(leads, per_subject, 1)
        take(heads, per_subject, 2)
        take(leads + heads, per_subject, 99)
        chosen += picked
    return [{"subject": c["subject"], "question": c["question"], "passage": c["passage"], "article": c["article"],
             "method": f"rule-based:{c['kind']}"} for c in chosen]


def write_sample_questions(pack: Path) -> list[dict[str, Any]]:
    passages = [json.loads(line) for line in (pack / "passages.jsonl").read_text(encoding="utf-8").splitlines() if line]
    items = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))["items"]
    kw = load_keyword_index(pack / "keyword.idx") if (pack / "keyword.idx").exists() else None
    qs = build_sample_questions(passages, [i for i in items if i.get("type") == "article"], kw)
    (pack / "sample-questions.json").write_text(json.dumps(qs, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return qs


def main(argv: list[str]) -> int:
    from pipeline.stages.assemble import OUT_DIR

    pack = Path(argv[0]) if argv else OUT_DIR / "dev"
    qs = write_sample_questions(pack)
    for q in qs:
        print(f"{q['subject']:9} {q['question']:55} -> {q['passage']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
