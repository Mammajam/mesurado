"""Timeline stage: build timeline.json from pipeline/timeline.yaml (spec: content-pipeline R10.3, map-and-timeline R3).

The source file lists events with a verbatim `quote` from a passage of the pack. The build finds that passage, takes the
whole sentence that contains the quote as the event summary (summaryType "copied") and fails if the quote is missing or
ambiguous, so no summary is ever our own wording and every event is traceable. The validator re-checks the result.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

from pipeline.text import split_sentences

TIMELINE_YAML = Path(__file__).resolve().parents[1] / "timeline.yaml"
# A summary shown on its own cannot start with a word that refers back to an earlier sentence.
_DANGLING_OPENERS = {"he", "she", "it", "they", "his", "her", "its", "their", "this", "these", "those", "however", "then"}
EVENT_KEYS = {"id", "era", "start", "end", "approx", "title", "passage", "quote", "place", "reviewed"}


class TimelineError(ValueError):
    pass


def containing_sentence(text: str, quote: str) -> str:
    """The sentence of `text` that contains `quote`; error if the quote is absent or appears more than once."""
    n = text.count(quote)
    if n != 1:
        raise TimelineError(f"quote {quote!r} appears {n} times in the passage (needs exactly 1)")
    pos = text.index(quote)
    for s, e in split_sentences(text):
        if s <= pos < e:
            first = text[s:e].split(maxsplit=1)[0].strip(",;:").lower()
            if first in _DANGLING_OPENERS:
                raise TimelineError(f"the sentence for {quote!r} starts with {first!r} and cannot stand alone; choose another quote")
            return text[s:e]
    raise TimelineError(f"quote {quote!r} is not inside a sentence")


def build_timeline(source: dict[str, Any], passages: dict[str, dict], skip_missing: bool = False,
                   places: set[str] | None = None) -> dict[str, Any]:
    """Events as timeline.json content. With skip_missing (subject-limited builds) events whose passage is not in the pack are
    dropped, and a place that is not in `places` is cleared; otherwise both are errors."""
    eras = source["eras"]
    era_ids = [e["id"] for e in eras]
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    dropped = 0
    for raw in source["events"]:
        extra = set(raw) - EVENT_KEYS
        if extra:
            errors.append(f"{raw.get('id')}: unknown keys {sorted(extra)}")
            continue
        eid = raw["id"]
        if eid in seen:
            errors.append(f"{eid}: duplicate id")
        seen.add(eid)
        if raw["era"] not in era_ids:
            errors.append(f"{eid}: unknown era {raw['era']!r}")
        p = passages.get(raw["passage"])
        if p is None and skip_missing:
            dropped += 1
            continue
        if p is None:
            errors.append(f"{eid}: passage {raw['passage']!r} is not in the pack")
            continue
        try:
            summary = containing_sentence(p["text"], raw["quote"])
        except TimelineError as exc:
            errors.append(f"{eid}: {exc}")
            continue
        events.append({
            "id": eid, "era": raw["era"], "start": raw["start"], "end": raw.get("end"), "approx": bool(raw.get("approx", False)),
            "title": raw["title"], "summary": summary, "summaryType": "copied", "passage": raw["passage"],
            "article": p["article"], "place": raw.get("place") if places is None or raw.get("place") in places else None, "subject": "history", "reviewed": bool(raw.get("reviewed", False)),
        })
    if errors:
        raise TimelineError("\n".join(errors))
    events.sort(key=lambda e: (e["start"], e["end"] if e["end"] is not None else e["start"], e["id"]))
    return {"format": "mesurado-timeline-1", "dropped": dropped, "eras": [{"id": e["id"], "name": e["name"], "until": e["until"]} for e in eras], "events": events}


def write_timeline(pack: Path, source_path: Path = TIMELINE_YAML, skip_missing: bool = False) -> int:
    """Write pack/timeline.json. Returns the number of events dropped because their passage is not in a partial pack."""
    source = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    passages = {}
    for line in (pack / "passages.jsonl").read_text(encoding="utf-8").splitlines():
        if line:
            p = json.loads(line)
            passages[p["id"]] = p
    items = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))["items"] if (pack / "manifest.json").exists() else []
    places = {i["id"] for i in items if i.get("coordinates")} if skip_missing else None
    tl = build_timeline(source, passages, skip_missing, places)
    dropped = tl.pop("dropped")
    (pack / "timeline.json").write_text(json.dumps(tl, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return dropped


def main(argv: list[str]) -> int:
    from pipeline.stages.assemble import OUT_DIR

    pack = Path(argv[0]) if argv else OUT_DIR / "dev"
    try:
        write_timeline(pack)
    except TimelineError as exc:
        print(exc)
        return 1
    print(f"{len(json.loads((pack / 'timeline.json').read_text(encoding='utf-8'))['events'])} events")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
