"""The pack checks (spec: content-pipeline R6, R9 to R11 and design "Validation checks").

validate(pack) is pure: it only reads the Pack it is given and returns a Report.
"""

from __future__ import annotations

import json
import re
import struct
from collections.abc import Iterable
from typing import Any

from .model import (
    DEFAULT_ALLOWED_LICENSES,
    FORBIDDEN_TERMS,
    PACK_LEVEL_FILES,
    REQUIRED_ITEM_FIELDS,
    Pack,
    Report,
    compute_content_hash,
    iter_chunks,
)

MIN_QUIZ_QUESTIONS = 200
MIN_SAMPLE_QUESTIONS_PER_SUBJECT = 10
_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip().casefold()


def _items(pack: Pack) -> list[dict[str, Any]]:
    m = pack.manifest
    items = m.get("items") if isinstance(m, dict) else None
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


# 1. Manifest entries -------------------------------------------------------------------------


def check_manifest(pack: Pack, report: Report, allowed: frozenset[str]) -> None:
    if pack.manifest is None:
        report.add("MANIFEST_MISSING", "manifest.json is missing or unreadable", "manifest.json")
        return
    if not isinstance(pack.manifest, dict) or not isinstance(pack.manifest.get("items"), list):
        report.add("MANIFEST_INVALID", "manifest.json must be an object with an `items` list", "manifest.json")
        return
    seen: set[str] = set()
    for n, item in enumerate(pack.manifest["items"]):
        where = str(item.get("id", f"items[{n}]")) if isinstance(item, dict) else f"items[{n}]"
        if not isinstance(item, dict):
            report.add("ITEM_INVALID", "manifest item is not an object", where)
            continue
        for f in REQUIRED_ITEM_FIELDS:
            v = item.get(f)
            missing = v is None or (isinstance(v, str) and not v.strip())
            if f == "modifications":
                missing = not isinstance(v, list)
            if missing:
                report.add("ITEM_FIELD_MISSING", f"missing required field `{f}`", where)
        lic = item.get("license")
        if isinstance(lic, str) and lic.strip() and lic not in allowed:
            report.add("LICENSE_NOT_ALLOWED", f"license `{lic}` is not on the allowed list", where)
        url = item.get("source_url")
        if isinstance(url, str) and url.strip() and not url.startswith(("http://", "https://")):
            report.add("SOURCE_URL_INVALID", "source_url must start with http:// or https://", where)
        iid = item.get("id")
        if isinstance(iid, str):
            if iid in seen:
                report.add("ITEM_DUPLICATE_ID", "duplicate manifest id", where)
            seen.add(iid)
        if item.get("type") == "article" and not item.get("text_file"):
            report.add("ITEM_FIELD_MISSING", "article item needs `text_file`", where)


# 2. Files and manifest agree ------------------------------------------------------------------


def check_files(pack: Pack, report: Report) -> None:
    referenced: set[str] = set()
    for item in _items(pack):
        for key in ("text_file", "file"):
            ref = item.get(key)
            if isinstance(ref, str) and ref:
                referenced.add(ref)
                if ref not in pack.files:
                    report.add("MANIFEST_FILE_MISSING", f"manifest lists `{ref}` but it is not in the pack", str(item.get("id")))
    for rel in sorted(pack.files):
        if rel in PACK_LEVEL_FILES or rel in referenced:
            continue
        report.add("FILE_NOT_IN_MANIFEST", f"`{rel}` has no manifest entry", rel)


# 3. Passages trace back to articles -----------------------------------------------------------


def check_passages(pack: Pack, report: Report) -> None:
    if pack.passages is None:
        report.add("PASSAGES_MISSING", "passages.jsonl is missing or unreadable", "passages.jsonl")
        return
    article_ids = {str(i.get("id")) for i in _items(pack) if i.get("type") == "article"}
    seen: set[str] = set()
    with_passages: set[str] = set()
    for p in pack.passages:
        pid = str(p.get("id")) if isinstance(p, dict) else "?"
        if not isinstance(p, dict):
            report.add("PASSAGE_INVALID", "passage is not an object", pid)
            continue
        if pid in seen:
            report.add("PASSAGE_DUPLICATE_ID", "duplicate passage id", pid)
        seen.add(pid)
        aid = p.get("article")
        if aid not in article_ids:
            report.add("PASSAGE_ORPHAN", f"article `{aid}` is not in the manifest", pid)
            continue
        with_passages.add(str(aid))
        text, start, end = p.get("text"), p.get("start"), p.get("end")
        art = pack.articles.get(str(aid))
        if not isinstance(text, str) or not isinstance(start, int) or not isinstance(end, int) or isinstance(start, bool):
            report.add("PASSAGE_INVALID", "passage needs text, integer start and end", pid)
            continue
        if art is None:
            report.add("ARTICLE_TEXT_MISSING", f"no text for article `{aid}`", pid)
            continue
        if not (0 <= start < end <= len(art)):
            report.add("PASSAGE_OFFSETS_INVALID", f"offsets {start}..{end} outside article of length {len(art)}", pid)
        elif art[start:end] != text:
            report.add("PASSAGE_TEXT_MISMATCH", "passage text differs from article[start:end]", pid)
    for aid in sorted(article_ids - with_passages):
        report.add("ARTICLE_WITHOUT_PASSAGES", "article has no passages", aid)


# 4. Forbidden terms ----------------------------------------------------------------------------


def _contains_term(src: bytes | Any, term: bytes) -> bool:
    tail = b""
    for chunk in iter_chunks(src):
        window = (tail + chunk).lower()
        if term in window:
            return True
        tail = window[-(len(term) - 1) :] if len(term) > 1 else b""
    return False


def check_forbidden_terms(pack: Pack, report: Report) -> None:
    for rel, src in sorted(pack.files.items()):
        for term in FORBIDDEN_TERMS:
            if _contains_term(src, term.encode("ascii")):
                report.add("FORBIDDEN_TERM", f"contains the forbidden term `{term}`", rel)
    # Packs built in memory without files (no file listing) are checked through their parsed content.
    if pack.files:
        return
    blobs: list[tuple[str, str]] = [(f"article:{k}", v) for k, v in pack.articles.items()]
    blobs += [(f"passage:{p.get('id')}", str(p.get("text", ""))) for p in (pack.passages or []) if isinstance(p, dict)]
    blobs += [("manifest", str(pack.manifest))]
    for where, text in blobs:
        low = text.lower()
        for term in FORBIDDEN_TERMS:
            if term in low and not any(i.code == "FORBIDDEN_TERM" and i.location == where for i in report.issues):
                report.add("FORBIDDEN_TERM", f"contains the forbidden term `{term}`", where)


# 5. Pack metadata hash -------------------------------------------------------------------------


def check_meta(pack: Pack, report: Report) -> None:
    if pack.meta is None:
        report.add("META_MISSING", "meta.json is missing or unreadable", "meta.json")
        return
    declared = pack.meta.get("content_hash") if isinstance(pack.meta, dict) else None
    if not isinstance(declared, str):
        report.add("META_FIELD_MISSING", "meta.json needs `content_hash`", "meta.json")
        return
    actual = compute_content_hash(pack.files)
    if declared != actual:
        report.add("META_HASH_MISMATCH", f"content_hash {declared[:12]}... does not match files ({actual[:12]}...)", "meta.json")


# 6. Sample questions ---------------------------------------------------------------------------


def check_sample_questions(pack: Pack, report: Report, passage_ids: set[str]) -> None:
    sq = pack.sample_questions
    if sq is None:
        return
    if not isinstance(sq, list):
        report.add("SAMPLE_QUESTIONS_INVALID", "sample-questions.json must be a list", "sample-questions.json")
        return
    per_subject: dict[str, int] = {}
    for n, q in enumerate(sq):
        where = f"sample-questions[{n}]"
        if not isinstance(q, dict) or not q.get("question") or not q.get("subject"):
            report.add("SAMPLE_QUESTIONS_INVALID", "needs `subject` and `question`", where)
            continue
        per_subject[q["subject"]] = per_subject.get(q["subject"], 0) + 1
        if q.get("passage") not in passage_ids:
            report.add("SAMPLE_QUESTION_BAD_PASSAGE", f"passage `{q.get('passage')}` does not exist", where)
    for subj, n in sorted(per_subject.items()):
        if n < MIN_SAMPLE_QUESTIONS_PER_SUBJECT:
            report.add("SAMPLE_QUESTIONS_FEW", f"only {n} sample questions for `{subj}`", "sample-questions.json", "warning")


# 7. Timeline -----------------------------------------------------------------------------------


def _valid_coordinates(c: Any) -> bool:
    try:
        lat, lon = float(c["lat"]), float(c["lon"])
    except (KeyError, TypeError, ValueError):
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180


def check_timeline(pack: Pack, report: Report, passage_ids: set[str]) -> None:
    tl = pack.timeline
    if tl is None:
        return
    events = tl.get("events") if isinstance(tl, dict) else tl
    if not isinstance(events, list):
        report.add("TIMELINE_INVALID", "timeline.json must be a list or have an `events` list", "timeline.json")
        return
    places = {str(i.get("id")): i for i in _items(pack)}
    seen: set[str] = set()
    for n, ev in enumerate(events):
        where = str(ev.get("id", f"events[{n}]")) if isinstance(ev, dict) else f"events[{n}]"
        if not isinstance(ev, dict):
            report.add("TIMELINE_INVALID", "event is not an object", where)
            continue
        if where in seen:
            report.add("TIMELINE_DUPLICATE_ID", "duplicate event id", where)
        seen.add(where)
        for f in ("title", "era", "summary"):
            if not ev.get(f):
                report.add("TIMELINE_FIELD_MISSING", f"missing `{f}`", where)
        start, end = ev.get("start"), ev.get("end")
        if not isinstance(start, int) or isinstance(start, bool):
            report.add("TIMELINE_BAD_DATE", "`start` must be an integer year (negative for BCE)", where)
        elif end is not None and (not isinstance(end, int) or isinstance(end, bool) or end < start):
            report.add("TIMELINE_BAD_DATE", "`end` must be an integer year not before `start`", where)
        if ev.get("passage") not in passage_ids:
            report.add("TIMELINE_BAD_PASSAGE", f"passage `{ev.get('passage')}` does not exist", where)
        place = ev.get("place")
        if place is not None:
            item = places.get(str(place))
            if item is None or not _valid_coordinates(item.get("coordinates")):
                report.add("TIMELINE_PLACE_NO_COORDINATES", f"place `{place}` has no valid coordinates in the manifest", where)


# 8. Quiz bank ----------------------------------------------------------------------------------

QUIZ_FIELDS = ("id", "subject", "topic", "difficulty", "type", "stem", "options", "answer", "explanation", "passage", "generation")


def check_quiz_bank(pack: Pack, report: Report) -> None:
    qb = pack.quiz_bank
    if qb is None:
        return
    questions = qb.get("questions") if isinstance(qb, dict) else qb
    if not isinstance(questions, list):
        report.add("QUIZ_INVALID", "quiz-bank.json must be a list or have a `questions` list", "quiz-bank.json")
        return
    passages = {str(p.get("id")): str(p.get("text", "")) for p in (pack.passages or []) if isinstance(p, dict)}
    seen: set[str] = set()
    for n, q in enumerate(questions):
        where = str(q.get("id", f"questions[{n}]")) if isinstance(q, dict) else f"questions[{n}]"
        if not isinstance(q, dict):
            report.add("QUIZ_INVALID", "question is not an object", where)
            continue
        if where in seen:
            report.add("QUIZ_DUPLICATE_ID", "duplicate question id", where)
        seen.add(where)
        for f in QUIZ_FIELDS:
            if q.get(f) in (None, "", []):
                report.add("QUIZ_FIELD_MISSING", f"missing `{f}`", where)
        if q.get("reviewed") is not True:
            report.add("QUIZ_UNREVIEWED", "only reviewed questions may ship (`reviewed` must be true)", where)
        opts = q.get("options")
        if not isinstance(opts, list) or len(opts) != 4 or not all(isinstance(o, str) for o in opts):
            report.add("QUIZ_BAD_OPTIONS", "needs exactly four string options", where)
            continue
        if len({_norm(o) for o in opts}) != 4:
            report.add("QUIZ_BAD_OPTIONS", "the four options must be distinct", where)
        ans = q.get("answer")
        if not isinstance(ans, int) or isinstance(ans, bool) or not 0 <= ans < 4:
            report.add("QUIZ_BAD_ANSWER", "`answer` must be an index 0 to 3", where)
            continue
        correct = opts[ans]
        pid = q.get("passage")
        if pid not in passages:
            report.add("QUIZ_BAD_PASSAGE", f"passage `{pid}` does not exist", where)
        elif _norm(correct) not in _norm(passages[str(pid)]):
            report.add("QUIZ_ANSWER_NOT_IN_PASSAGE", "the correct option does not appear in its passage", where)
        stem = _norm(str(q.get("stem", "")))
        if _norm(correct) and _norm(correct) in stem:
            report.add("QUIZ_ANSWER_LEAK", "the stem contains the correct answer", where)
        for i, o in enumerate(opts):
            if i != ans and _norm(o) and _norm(o) in stem:
                report.add("QUIZ_DISTRACTOR_IN_STEM", f"distractor `{o}` appears in the stem", where)
    if len(questions) < MIN_QUIZ_QUESTIONS:
        report.add("QUIZ_BANK_SMALL", f"{len(questions)} questions, target is {MIN_QUIZ_QUESTIONS}", "quiz-bank.json", "warning")


# 7. Search indexes -----------------------------------------------------------------------------


def _file_bytes(pack: Pack, rel: str) -> bytes | None:
    src = pack.files.get(rel)
    if src is None:
        return None
    return src if isinstance(src, bytes) else src.read_bytes()


def check_indexes(pack: Pack, report: Report, passage_ids: list[str]) -> None:
    """keyword.idx and embeddings.i8 are optional, but when present they must describe exactly the passages."""
    raw = _file_bytes(pack, "keyword.idx")
    if raw is not None:
        try:
            idx = json.loads(raw)
            if idx.get("format") != "mesurado-keyword-1":
                report.add("KEYWORD_INDEX_INVALID", f"unknown format {idx.get('format')!r}", "keyword.idx")
            elif idx.get("doc_ids") != passage_ids:
                report.add("KEYWORD_INDEX_MISMATCH", "doc_ids differ from passages.jsonl (count or order)", "keyword.idx")
            elif len(idx.get("doc_len", [])) != len(passage_ids) or idx.get("n_docs") != len(passage_ids):
                report.add("KEYWORD_INDEX_INVALID", "n_docs or doc_len length does not match the passages", "keyword.idx")
        except (ValueError, AttributeError):
            report.add("KEYWORD_INDEX_INVALID", "keyword.idx is not valid JSON", "keyword.idx")
    raw = _file_bytes(pack, "embeddings.i8")
    if raw is not None:
        try:
            if raw[:4] != b"MSE1":
                raise ValueError("bad magic")
            (hlen,) = struct.unpack("<I", raw[4:8])
            h = json.loads(raw[8:8 + hlen])
            n, d = int(h["count"]), int(h["dims"])
            if len(raw) != 8 + hlen + 4 * n + n * d:
                report.add("EMBEDDINGS_INVALID", "file size does not match the header", "embeddings.i8")
            elif n != len(passage_ids):
                report.add("EMBEDDINGS_MISMATCH", f"{n} vectors for {len(passage_ids)} passages", "embeddings.i8")
            elif n and (h.get("first_id") != passage_ids[0] or h.get("last_id") != passage_ids[-1]):
                report.add("EMBEDDINGS_MISMATCH", "first/last passage id differ from passages.jsonl", "embeddings.i8")
            elif not h.get("model") or not h.get("license"):
                report.add("EMBEDDINGS_INVALID", "header must name the model and its license", "embeddings.i8")
        except (ValueError, KeyError, TypeError, struct.error):
            report.add("EMBEDDINGS_INVALID", "unreadable embeddings header", "embeddings.i8")


# 8. ZIM container ------------------------------------------------------------------------------

ZIM_FILE = "mesurado.zim"


def check_zim(pack: Pack, report: Report) -> None:
    """If a ZIM is present, every manifest article must be in it, byte for byte, and nothing else (R5.1)."""
    src = pack.files.get(ZIM_FILE)
    if src is None:
        return
    if isinstance(src, bytes):
        report.add("ZIM_UNREADABLE", "ZIM given as bytes; expected a file on disk", ZIM_FILE)
        return
    try:
        from libzim.reader import Archive
    except ImportError:
        report.add("ZIM_NOT_CHECKED", "python-libzim is not installed; ZIM contents not checked", ZIM_FILE, "warning")
        return
    try:
        zim = Archive(src)
    except Exception as exc:  # libzim raises RuntimeError for corrupt files
        report.add("ZIM_UNREADABLE", f"cannot open ZIM: {exc}", ZIM_FILE)
        return
    expected: dict[str, bytes] = {}
    for item in _items(pack):
        ref = item.get("text_file")
        if item.get("type") == "article" and isinstance(ref, str) and ref in pack.files:
            expected[ref] = _file_bytes(pack, ref) or b""
    in_zim = {zim.get_entry_by_id(i).path for i in range(zim.all_entry_count)}
    for ref, data in sorted(expected.items()):
        if ref not in in_zim:
            report.add("ZIM_ENTRY_MISSING", f"`{ref}` is not in the ZIM", ZIM_FILE)
        elif bytes(zim.get_entry_by_path(ref).get_item().content) != data:
            report.add("ZIM_ENTRY_MISMATCH", f"`{ref}` differs from the pack file", ZIM_FILE)
    # libzim adds its own entries (metadata, listing/...); only pack content under articles/ is checked.
    for extra in sorted(p for p in in_zim if p.startswith("articles/") and p not in expected):
        report.add("ZIM_ENTRY_EXTRA", f"`{extra}` is in the ZIM but not in the manifest", ZIM_FILE)


# Entry point -----------------------------------------------------------------------------------


def validate(pack: Pack, allowed_licenses: Iterable[str] | None = None) -> Report:
    allowed = frozenset(allowed_licenses) if allowed_licenses is not None else DEFAULT_ALLOWED_LICENSES
    report = Report()
    report.issues.extend(pack.load_errors)
    check_manifest(pack, report, allowed)
    check_files(pack, report)
    check_passages(pack, report)
    check_forbidden_terms(pack, report)
    check_meta(pack, report)
    passage_ids = {str(p.get("id")) for p in (pack.passages or []) if isinstance(p, dict)}
    check_sample_questions(pack, report, passage_ids)
    check_timeline(pack, report, passage_ids)
    check_quiz_bank(pack, report)
    check_indexes(pack, report, [str(p.get("id")) for p in (pack.passages or []) if isinstance(p, dict)])
    check_zim(pack, report)

    items = _items(pack)
    licenses: dict[str, int] = {}
    for i in items:
        licenses[str(i.get("license"))] = licenses.get(str(i.get("license")), 0) + 1
    report.counts = {
        "items": len(items),
        "articles": sum(1 for i in items if i.get("type") == "article"),
        "passages": len(pack.passages or []),
        "files": len(pack.files),
        "distinct_licenses": len(licenses),
        "errors": len(report.errors),
        "warnings": len(report.warnings),
    }
    return report


def validate_path(path: str, allowed_licenses: Iterable[str] | None = None) -> Report:
    from .loader import load_pack

    return validate(load_pack(path), allowed_licenses)
