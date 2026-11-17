"""One-command pack build (spec: content-pipeline R8.2, R8.3, R6).

    uv run --python 3.12 python -m pipeline.build [--subjects history,geography] [--offline]

Stages, in order, each printing its name and time:
  select     read selection.yaml, check sources and licenses
  fetch      resolve titles to pinned revisions and download them (cached; --offline forbids any network call)
  clean      HTML to plain text blocks
  passages   split into citable passages
  assemble   pack directory: articles, manifest, attribution, timeline, quiz bank, fallback map, indexes and embeddings,
             sample questions, ZIM, then the validator. The pack replaces the previous one only if validation passes.

A build limited with --subjects writes to pipeline/out/dev-<subjects> and never replaces the full pack. Reruns reuse the
fetch cache and the embedding cache, so only changed articles are fetched and embedded again.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.selection import DEFAULT_SELECTION, load_selection
from pipeline.stages import fetch as F
from pipeline.stages.assemble import OUT_DIR, assemble
from pipeline.stages.clean import clean_all
from pipeline.stages.passages import split_all

PIPELINE_DIR = Path(__file__).resolve().parent


class StageError(RuntimeError):
    """A stage failed; the message says what to fix."""


def _offline_http(params: dict[str, str]) -> dict[str, Any]:
    raise F.FetchError("offline mode: a network call was needed but is not allowed (add the article to the cache first)")


@dataclass
class BuildConfig:
    subjects: list[str] | None = None
    offline: bool = False
    selection_path: Path = DEFAULT_SELECTION
    pins_path: Path = F.PINS_PATH
    fetch_cache: Path = F.CACHE_DIR
    work_root: Path = PIPELINE_DIR / "work"
    out_dir: Path = OUT_DIR
    embed_cache: Path = PIPELINE_DIR / "cache" / "embeddings" / "minilm.npz"
    timeline_source: Path | None = None
    reviewed_path: Path | None = None
    http_get: Callable[[dict[str, str]], dict[str, Any]] | None = None
    embedder: Any = None
    log: Callable[[str], None] = lambda s: print(s, flush=True)

    @property
    def partial(self) -> bool:
        return bool(self.subjects)

    @property
    def pack_name(self) -> str:
        return "dev-" + "-".join(sorted(self.subjects)) if self.subjects else "dev"


@dataclass
class BuildResult:
    ok: bool = False
    pack: Path | None = None
    stages: list[tuple[str, float, str]] = field(default_factory=list)  # (name, seconds, summary)
    error: str = ""
    report: Any = None


def stage_select(cfg: BuildConfig, state: dict[str, Any]) -> str:
    sel = load_selection(cfg.selection_path)
    chosen = sel.articles(cfg.subjects)  # raises SelectionError for an unknown subject
    state["selection"] = sel
    return f"{len(chosen)} articles in {len({a.subject for a in chosen})} subject(s)"


def stage_fetch(cfg: BuildConfig, state: dict[str, Any]) -> str:
    http = cfg.http_get or (_offline_http if cfg.offline else F.default_http_get)
    res = F.fetch(state["selection"], cfg.subjects, http_get=http, pins_path=cfg.pins_path, cache_dir=cfg.fetch_cache,
                  work_dir=cfg.work_root / "fetch", log=cfg.log)
    if not res.ok:
        raise StageError("fetch problems:\n  " + "\n  ".join(res.problems))
    return f"{len(res.items)} articles ({res.new_pins} new pins)"


def stage_clean(cfg: BuildConfig, state: dict[str, Any]) -> str:
    arts = clean_all(cfg.work_root / "fetch", cfg.work_root / "clean")
    empty = [a.id for a in arts if a.stats["words"] == 0]
    if empty:
        raise StageError(f"no text after cleaning: {empty}")
    return f"{len(arts)} articles, {sum(a.stats['words'] for a in arts):,} words"


def stage_passages(cfg: BuildConfig, state: dict[str, Any]) -> str:
    passages, empty = split_all(cfg.work_root / "clean", cfg.work_root / "passages")
    state["passages_without"] = empty
    note = f"; {len(empty)} article(s) without passages dropped: {empty}" if empty else ""
    return f"{len(passages)} passages{note}"


def stage_assemble(cfg: BuildConfig, state: dict[str, Any]) -> str:
    path, report = assemble(
        cfg.pack_name, cfg.out_dir, cfg.embedder, fetch_dir=cfg.work_root / "fetch", clean_dir=cfg.work_root / "clean",
        passages_dir=cfg.work_root / "passages", timeline_source=cfg.timeline_source, reviewed_path=cfg.reviewed_path,
        embed_cache=cfg.embed_cache, partial=cfg.partial, log=cfg.log,
    )
    state["report"] = report
    if path is None:
        raise StageError("validation failed; the previous pack was not replaced:\n" + report.format())
    state["pack"] = path
    size = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    return f"{path.name}: {report.counts.get('articles', 0)} articles, {report.counts.get('passages', 0)} passages, {size / 1e6:.1f} MB, {len(report.warnings)} warning(s)"


STAGES: list[tuple[str, Callable[[BuildConfig, dict[str, Any]], str]]] = [
    ("select", stage_select), ("fetch", stage_fetch), ("clean", stage_clean), ("passages", stage_passages), ("assemble", stage_assemble),
]


def run_build(cfg: BuildConfig, stages=STAGES) -> BuildResult:
    result = BuildResult()
    state: dict[str, Any] = {}
    for n, (name, fn) in enumerate(stages, start=1):
        cfg.log(f"[{n}/{len(stages)}] {name} ...")
        t0 = time.monotonic()
        try:
            summary = fn(cfg, state)
        except Exception as exc:  # any stage failure stops the build; earlier output stays, the pack is never half-replaced
            result.stages.append((name, time.monotonic() - t0, "FAILED"))
            result.error = f"stage `{name}` failed: {exc}"
            result.report = state.get("report")
            return result
        result.stages.append((name, time.monotonic() - t0, summary))
        cfg.log(f"      {summary}")
    result.ok = True
    result.pack = state.get("pack")
    result.report = state.get("report")
    return result


def format_summary(result: BuildResult) -> str:
    lines = ["", "Build summary", "-------------"]
    for name, secs, summary in result.stages:
        lines.append(f"  {name:9} {secs:6.1f}s  {summary.splitlines()[0]}")
    lines.append(f"  total     {sum(s for _, s, _ in result.stages):6.1f}s")
    if result.ok and result.report is not None:
        lines.append(f"Pack: {result.pack}")
        for w in result.report.warnings:
            lines.append(f"  WARNING {w.code}: {w.message}")
    elif result.error:
        lines.append("BUILD FAILED")
        lines.append(result.error)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pipeline.build", description="Build the Mesurado content pack.")
    ap.add_argument("--subjects", help="comma-separated subjects to build (writes pipeline/out/dev-<subjects>, not the full pack)")
    ap.add_argument("--offline", action="store_true", help="fail instead of using the network; use pins and caches only")
    ns = ap.parse_args(argv)
    cfg = BuildConfig(subjects=ns.subjects.split(",") if ns.subjects else None, offline=ns.offline)
    result = run_build(cfg)
    print(format_summary(result))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
