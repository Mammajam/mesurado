"""Data types for the pack validator (spec: content-pipeline R6, design "Validation checks")."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Licenses allowed in the pack. Content licenses first, then data and font licenses used by the map pack.
DEFAULT_ALLOWED_LICENSES: frozenset[str] = frozenset(
    {
        "CC-BY-SA-4.0",
        "CC-BY-SA-3.0",
        "CC-BY-4.0",
        "CC-BY-3.0",
        "CC0-1.0",
        "PD",  # public domain, for example Natural Earth
        "ODbL-1.0",  # OpenStreetMap data
        "OFL-1.1",  # fonts
    }
)

REQUIRED_ITEM_FIELDS: tuple[str, ...] = (
    "id",
    "type",
    "title",
    "source_url",
    "revision",
    "license",
    "attribution",
    "retrieved_at",
    "modifications",
)

# Files that may live in a pack without a manifest entry (they describe or index the pack itself).
PACK_LEVEL_FILES: frozenset[str] = frozenset(
    {
        "manifest.json",
        "meta.json",
        "passages.jsonl",
        "attribution.md",
        "attribution.json",
        "sample-questions.json",
        "timeline.json",
        "quiz-bank.json",
        "keyword.idx",
        "embeddings.i8",
        "mesurado.zim",
        "map-style.json",
        "fallback-map.svg",
    }
)

FORBIDDEN_TERMS: tuple[str, ...] = ("encarta",)


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    location: str = ""
    severity: str = "error"  # "error" fails the build, "warning" does not

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "location": self.location,
            "message": self.message,
        }


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def error_codes(self) -> set[str]:
        return {i.code for i in self.errors}

    def add(self, code: str, message: str, location: str = "", severity: str = "error") -> None:
        self.issues.append(Issue(code, message, location, severity))

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "counts": self.counts,
            "errors": [i.as_dict() for i in self.errors],
            "warnings": [i.as_dict() for i in self.warnings],
        }

    def format(self, limit: int = 50) -> str:
        lines = [f"Pack validation: {'PASS' if self.ok else 'FAIL'}"]
        for k in sorted(self.counts):
            lines.append(f"  {k}: {self.counts[k]}")
        shown = 0
        for i in self.issues:
            if shown >= limit:
                lines.append(f"  ... {len(self.issues) - limit} more issues not shown")
                break
            where = f" [{i.location}]" if i.location else ""
            lines.append(f"  {i.severity.upper()} {i.code}{where}: {i.message}")
            shown += 1
        return "\n".join(lines)


@dataclass
class Pack:
    """An unpacked pack, either loaded from a directory or built in memory for tests.

    files maps a relative path (forward slashes) to its bytes (in memory) or to a Path on disk.
    """

    manifest: Any = None
    passages: list[dict[str, Any]] | None = None
    articles: dict[str, str] = field(default_factory=dict)  # article id -> cleaned text
    meta: dict[str, Any] | None = None
    sample_questions: Any = None
    timeline: Any = None
    quiz_bank: Any = None
    files: dict[str, bytes | Path] = field(default_factory=dict)
    load_errors: list[Issue] = field(default_factory=list)


def iter_chunks(src: bytes | Path, size: int = 1 << 20):
    if isinstance(src, bytes):
        yield src
        return
    with open(src, "rb") as fh:
        while True:
            chunk = fh.read(size)
            if not chunk:
                return
            yield chunk


def file_sha256(src: bytes | Path) -> str:
    h = hashlib.sha256()
    for chunk in iter_chunks(src):
        h.update(chunk)
    return h.hexdigest()


def compute_content_hash(files: dict[str, bytes | Path]) -> str:
    """Hash of every file except meta.json and the ZIM, over sorted (path, file hash) pairs.

    The ZIM is excluded because libzim writes a random UUID, so its bytes differ between builds of the same
    content; its entries are checked against the hashed files instead (check_zim).
    """
    h = hashlib.sha256()
    for rel in sorted(p for p in files if p != "meta.json" and not p.endswith(".zim")):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(file_sha256(files[rel]).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()
