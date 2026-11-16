"""Load and check pipeline/selection.yaml (spec: content-pipeline R1).

The file groups source articles by subject, so pack v1 can be built from history and geography
only, and science and mathematics added later without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from pipeline.validate.model import DEFAULT_ALLOWED_LICENSES

# Sources the pipeline knows how to fetch and that are openly licensed (license-record steering).
ALLOWED_SOURCES: frozenset[str] = frozenset({"wikipedia"})
DEFAULT_SELECTION = Path(__file__).with_name("selection.yaml")


class SelectionError(ValueError):
    """The selection file is invalid (R1.3: stop with an error naming the source)."""


@dataclass(frozen=True)
class SelectedArticle:
    subject: str
    source: str
    title: str


@dataclass(frozen=True)
class Selection:
    subjects: dict[str, list[SelectedArticle]]
    allowed_licenses: frozenset[str]

    def articles(self, only: list[str] | None = None) -> list[SelectedArticle]:
        names = only if only else list(self.subjects)
        unknown = [n for n in names if n not in self.subjects]
        if unknown:
            raise SelectionError(f"unknown subject(s): {', '.join(unknown)}; have {', '.join(self.subjects)}")
        return [a for n in names for a in self.subjects[n]]


def parse_selection(data: Any) -> Selection:
    if not isinstance(data, dict) or not isinstance(data.get("subjects"), dict) or not data["subjects"]:
        raise SelectionError("selection must have a non-empty `subjects` mapping")
    licenses = data.get("allowed_licenses", sorted(DEFAULT_ALLOWED_LICENSES))
    if not isinstance(licenses, list) or not all(isinstance(x, str) for x in licenses):
        raise SelectionError("`allowed_licenses` must be a list of SPDX ids")
    bad_lic = sorted(set(licenses) - DEFAULT_ALLOWED_LICENSES)
    if bad_lic:
        raise SelectionError(f"license(s) not allowed by the project: {', '.join(bad_lic)}")

    subjects: dict[str, list[SelectedArticle]] = {}
    seen: dict[tuple[str, str], str] = {}
    for subject, body in data["subjects"].items():
        arts = body.get("articles") if isinstance(body, dict) else None
        if not isinstance(arts, list) or not arts:
            raise SelectionError(f"subject `{subject}` needs a non-empty `articles` list")
        out: list[SelectedArticle] = []
        for n, a in enumerate(arts):
            if not isinstance(a, dict) or not a.get("title") or not a.get("source"):
                raise SelectionError(f"{subject}[{n}] needs `source` and `title`")
            extra = sorted(set(a) - {"source", "title"})
            if extra:
                raise SelectionError(
                    f"{subject}[{n}] `{a['title']}` has unexpected key(s) {extra}; "
                    "quote titles that contain commas or colons"
                )
            if a["source"] not in ALLOWED_SOURCES:
                raise SelectionError(
                    f"{subject}[{n}] `{a['title']}`: source `{a['source']}` is not allowed "
                    f"(allowed: {', '.join(sorted(ALLOWED_SOURCES))})"
                )
            key = (a["source"], str(a["title"]).replace("_", " ").strip().casefold())
            if key in seen:
                raise SelectionError(f"duplicate article `{a['title']}` in `{subject}` and `{seen[key]}`")
            seen[key] = subject
            out.append(SelectedArticle(subject, a["source"], str(a["title"]).replace("_", " ").strip()))
        subjects[str(subject)] = out
    return Selection(subjects, frozenset(licenses))


def load_selection(path: str | Path = DEFAULT_SELECTION) -> Selection:
    with open(path, encoding="utf-8") as fh:
        return parse_selection(yaml.safe_load(fh))


if __name__ == "__main__":
    sel = load_selection()
    for name, arts in sel.subjects.items():
        print(f"{name}: {len(arts)} articles")
