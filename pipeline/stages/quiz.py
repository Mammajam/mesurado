"""Quiz stage: build quiz-bank.json from reviewed questions and generate candidates for review (spec: content-pipeline R11).

Files (all under pipeline/quiz/):
  candidates.yaml  written by `generate`; the reviewer sets `status: accepted` or `rejected` (and may edit text). Never goes into the pack.
  reviewed.yaml    written by `promote` from accepted candidates, with `reviewed: true`. The only source of quiz-bank.json.

Nothing is marked reviewed by code: `promote` only moves entries a person has accepted. The validator refuses any
question that is not `reviewed: true`, whose answer is not in its passage, or that has fewer or more than four options.

Candidate rules (deterministic, no model):
  cloze-year   a stand-alone sentence with exactly one year; the year is blanked; distractors are the nearest other years
               used elsewhere in the same subject.
  cloze-title  a stand-alone sentence that names another article of the pack (a person or a thing); the title is blanked;
               distractors are titles of the same kind (person or thing) in the same subject.

Usage:  python -m pipeline.stages.quiz generate | promote [--reviewer NAME] | build [PACK_DIR]
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from pipeline.stages.questions import lead_question
from pipeline.text import split_sentences

QUIZ_DIR = Path(__file__).resolve().parents[1] / "quiz"
CANDIDATES = QUIZ_DIR / "candidates.yaml"
REVIEWED = QUIZ_DIR / "reviewed.yaml"
BLANK = "_____"
PER_SUBJECT = 150
PER_ARTICLE = 3
MIN_SENTENCE, MAX_SENTENCE = 60, 220
_YEAR = re.compile(r"(?<!\d)(?<!\d,)(?<!\d\.)(1[0-9]{3}|20[0-2][0-9])(?!\d)(?!,\d)")
_OPENERS = {"he", "she", "it", "they", "his", "her", "its", "their", "this", "these", "those", "however", "then", "also", "later"}
BANK_FIELDS = ("id", "subject", "topic", "difficulty", "type", "stem", "options", "answer", "explanation", "explanationType", "passage", "generation", "reviewed")


def _h(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12], 16)


def stand_alone(sentence: str) -> bool:
    first = sentence.split(maxsplit=1)[0].strip(",;:").lower() if sentence.strip() else ""
    return (MIN_SENTENCE <= len(sentence) <= MAX_SENTENCE and sentence[0].isupper() and first not in _OPENERS
            and sentence.count('"') % 2 == 0 and "\n" not in sentence
            and "(" not in sentence and sum(ch.isdigit() for ch in sentence) <= 8)  # no statistics-heavy sentences


def title_kinds(items: list[dict], passages: list[dict]) -> dict[str, str]:
    """'person' (the lead sentence defines a person) or 'place' (the manifest has coordinates) for an article.

    Articles that are neither are left out: a blanked title is only a fair question when the distractors are of the
    same kind (a person among people, a place among places).
    """
    lead = {p["article"]: p["text"] for p in passages if not p["heading_path"]}
    kinds = {}
    for it in items:
        text = lead.get(it["id"], "")
        spans = split_sentences(text) if text else []
        q = lead_question(it["title"], text[:spans[0][1]]) if spans else None
        if q and q.startswith("Who"):
            kinds[it["id"]] = "person"
        elif it.get("coordinates"):
            kinds[it["id"]] = "place"
    return kinds


def display_title(title: str) -> str:
    return title.split(" (")[0]  # "Charles Taylor (Liberian politician)" is written "Charles Taylor" in running text


def make_candidates(passages: list[dict], items: list[dict], per_subject: int = PER_SUBJECT) -> list[dict[str, Any]]:
    arts = {i["id"]: i for i in items if i.get("type") == "article"}
    kinds = title_kinds(list(arts.values()), passages)
    by_subject_titles: dict[tuple[str, str], list[str]] = {}
    for a in arts.values():
        if a["id"] in kinds:
            by_subject_titles.setdefault((a["subject"], kinds[a["id"]]), []).append(display_title(a["title"]))
    years_by_subject: dict[str, set[int]] = {}
    sentences: list[tuple[dict, dict, str]] = []
    for p in passages:
        art = arts.get(p["article"])
        if not art:
            continue
        for s, e in split_sentences(p["text"]):
            sent = p["text"][s:e]
            years_by_subject.setdefault(art["subject"], set()).update(int(y) for y in _YEAR.findall(sent))
            if stand_alone(sent):
                sentences.append((p, art, sent))

    cands: list[dict[str, Any]] = []
    for p, art, sent in sentences:
        passage_text = p["text"]
        years = _YEAR.findall(sent)
        if len(set(years)) == 1 and len(years) == 1:
            answer = years[0]
            pool = sorted((y for y in years_by_subject[art["subject"]] if str(y) not in passage_text), key=lambda y: (abs(y - int(answer)), y))
            distractors = [str(y) for y in pool[:3]]
            stem_sentence = sent.replace(answer, BLANK, 1)
            if len(distractors) == 3 and not any(d in stem_sentence for d in distractors):
                cands.append(_candidate(p, art, "cloze-year", stem_sentence, answer, distractors, sent, "easy" if not p["heading_path"] else "medium"))
        for other in arts.values():
            title = display_title(other["title"])
            if other["id"] not in kinds or other["id"] == art["id"] or len(title) < 4 or title in {"Africa", "Liberia"}:
                continue
            whole_word = re.compile(r"(?<![\w-])" + re.escape(title) + r"(?!\w)")
            if len(whole_word.findall(sent)) != 1:
                continue  # absent, repeated, or only part of a longer word ("Sahara" inside "Saharan")
            last = title.split()[-1]
            pool = sorted((t for t in by_subject_titles[(other["subject"], kinds[other["id"]])] if t != title and t not in passage_text),
                          key=lambda t: (t.split()[-1] != last, abs(len(t) - len(title)), t))  # "X County" prefers other counties
            distractors = pool[:3]
            stem_sentence = whole_word.sub(BLANK, sent, count=1)
            if len(distractors) == 3 and not any(d in stem_sentence for d in distractors):
                cands.append(_candidate(p, art, "cloze-title", stem_sentence, title, distractors, sent, "medium"))
                break  # one question per sentence

    # Deterministic, spread selection: at most PER_ARTICLE per article, PER_SUBJECT per subject, ordered by hash.
    cands.sort(key=lambda c: _h(c["id"]))
    chosen: list[dict[str, Any]] = []
    for subject in sorted({c["subject"] for c in cands}):
        per_article: dict[str, int] = {}
        taken = 0
        for c in (c for c in cands if c["subject"] == subject):
            art = c["passage"].split("#")[0]
            if taken < per_subject and per_article.get(art, 0) < PER_ARTICLE:
                chosen.append(c)
                per_article[art] = per_article.get(art, 0) + 1
                taken += 1
    return sorted(chosen, key=lambda c: c["id"])


def _candidate(p: dict, art: dict, kind: str, stem_sentence: str, answer: str, distractors: list[str], sentence: str, difficulty: str) -> dict[str, Any]:
    cid = f"q-{_h(p['id'], str(p['start']), sentence, kind):012x}"
    pos = _h(cid, "position") % 4
    options = distractors[:pos] + [answer] + distractors[pos:]
    return {
        "id": cid, "subject": art["subject"], "topic": art["title"], "difficulty": difficulty, "type": kind,
        "stem": f"Fill in the blank: {stem_sentence}", "options": options, "answer": pos,
        "explanation": sentence, "explanationType": "copied", "passage": p["id"], "generation": "rule",
        "status": "pending",
    }


# ---- files ---------------------------------------------------------------------------------


def _dump(path: Path, header: str, key: str, rows: list[dict[str, Any]]) -> None:
    body = yaml.safe_dump({key: rows}, sort_keys=False, allow_unicode=True, width=1000)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + body, encoding="utf-8")


def _load(path: Path, key: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get(key) or []


def write_candidates(new: list[dict[str, Any]], path: Path = CANDIDATES) -> tuple[int, int]:
    """Merge into candidates.yaml without touching entries a reviewer already has: existing ids are kept as they are."""
    existing = _load(path, "candidates")
    known = {c["id"] for c in existing}
    added = [c for c in new if c["id"] not in known]
    header = ("# Quiz candidates (generated). Set `status: accepted` or `status: rejected` for each; edit stem, options, answer or\n"
              "# explanation if needed (keep the answer text inside the passage). Then run `python -m pipeline.stages.quiz promote`.\n"
              "# These are never shipped: only reviewed.yaml reaches the pack.\n")
    _dump(path, header, "candidates", existing + added)
    return len(added), len(existing)


def promote(candidates_path: Path = CANDIDATES, reviewed_path: Path = REVIEWED, reviewer: str = "", today: str | None = None) -> int:
    """Move accepted candidates into reviewed.yaml with reviewed: true. Returns how many were promoted."""
    cands = _load(candidates_path, "candidates")
    reviewed = _load(reviewed_path, "questions")
    have = {q["id"] for q in reviewed}
    moved = 0
    for c in cands:
        if c.get("status") == "accepted" and c["id"] not in have:
            q = {k: v for k, v in c.items() if k != "status"}
            q.update(reviewed=True, reviewed_on=today or date.today().isoformat())
            if reviewer:
                q["reviewer"] = reviewer
            reviewed.append(q)
            c["status"] = "promoted"
            moved += 1
    if moved:
        _dump(reviewed_path, "# Reviewed quiz questions: the only source of quiz-bank.json. Added by `promote` from accepted candidates.\n", "questions", reviewed)
        _dump(candidates_path, "# Quiz candidates (generated). Set `status: accepted` or `status: rejected`; run `promote` to move accepted ones.\n", "candidates", cands)
    return moved


def build_bank(reviewed: list[dict[str, Any]]) -> dict[str, Any]:
    """quiz-bank.json content from reviewed questions. Fields outside BANK_FIELDS (reviewer, dates, status) stay in the repo."""
    questions = [{k: q[k] for k in BANK_FIELDS if k in q} for q in sorted(reviewed, key=lambda q: q["id"])]
    return {"format": "mesurado-quiz-1", "questions": questions}


def write_quiz_bank(pack: Path, reviewed_path: Path = REVIEWED) -> int:
    """Write pack/quiz-bank.json if there are reviewed questions; returns how many. No questions, no file."""
    reviewed = _load(reviewed_path, "questions")
    if not reviewed:
        return 0
    (pack / "quiz-bank.json").write_text(json.dumps(build_bank(reviewed), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(reviewed)


def _pack_data(pack: Path) -> tuple[list[dict], list[dict]]:
    passages = [json.loads(line) for line in (pack / "passages.jsonl").read_text(encoding="utf-8").splitlines() if line]
    items = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))["items"]
    return passages, items


def main(argv: list[str]) -> int:
    from pipeline.stages.assemble import OUT_DIR

    cmd = argv[0] if argv else "generate"
    if cmd == "generate":
        pack = Path(argv[1]) if len(argv) > 1 else OUT_DIR / "dev"
        passages, items = _pack_data(pack)
        added, kept = write_candidates(make_candidates(passages, items))
        print(f"{added} new candidates added, {kept} already in {CANDIDATES.name}")
    elif cmd == "promote":
        reviewer = argv[argv.index("--reviewer") + 1] if "--reviewer" in argv else ""
        print(f"{promote(reviewer=reviewer)} questions promoted to {REVIEWED.name}")
    elif cmd == "build":
        pack = Path(argv[1]) if len(argv) > 1 else OUT_DIR / "dev"
        print(f"{write_quiz_bank(pack)} reviewed questions written to the pack")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
