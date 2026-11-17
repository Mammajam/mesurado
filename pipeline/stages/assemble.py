"""Assemble stage: write the unpacked pack directory and validate it (spec: content-pipeline R5.3, R5.4, R6).

Layout of pipeline/out/<name>/ (index and package stages add the indexes and the ZIM):
  manifest.json   items with source, license, revision, attribution, text_file
  passages.jsonl  one passage per line
  articles/*.txt  cleaned article text (what passage offsets point into)
  meta.json       version, counts, content hash

The pack is built in a temporary directory and moved into place only if the validator passes, so a failed
run never replaces a good pack.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date
from pathlib import Path

from pipeline.stages.clean import CLEAN_DIR
from pipeline.stages.fetch import WORK_DIR as FETCH_DIR
from pipeline.stages.fetch import slug
from pipeline.stages.passages import PASSAGES_DIR
from pipeline.validate import compute_content_hash, load_pack, validate
from pipeline.validate.model import Report

OUT_DIR = Path(__file__).resolve().parents[1] / "out"


def assemble(name: str = "dev", out_dir: Path = OUT_DIR, embedder=None, with_index: bool = True, with_zim: bool = True) -> tuple[Path | None, Report]:
    items = json.loads((FETCH_DIR / "items.json").read_text(encoding="utf-8"))["items"]
    passages = [json.loads(line) for line in (PASSAGES_DIR / "passages.jsonl").read_text(encoding="utf-8").splitlines() if line]
    have_passages = {p["article"] for p in passages}

    tmp = out_dir / f"{name}.tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "articles").mkdir(parents=True)

    manifest_items = []
    for item in items:
        if item["id"] not in have_passages:
            continue  # R3.5: an article with no passages is dropped from the pack
        clean = json.loads(next((CLEAN_DIR / item["subject"]).glob(f"{slug(item['id'])}.json")).read_text(encoding="utf-8"))
        rel = f"articles/{slug(item['id'])}.txt"
        (tmp / rel).write_text(clean["text"], encoding="utf-8")
        manifest_items.append({**item, "text_file": rel})

    (tmp / "manifest.json").write_text(json.dumps({"items": manifest_items}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    kept = [p for p in passages if p["article"] in {i["id"] for i in manifest_items}]
    (tmp / "passages.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in kept) + "\n", encoding="utf-8")

    index_stats = {}
    if with_index:  # before the content hash, so the hash covers the index files
        from pipeline.stages.index import build_indexes

        index_stats = build_indexes(tmp, embedder)

    files = {p.relative_to(tmp).as_posix(): p for p in tmp.rglob("*") if p.is_file()}
    meta = {
        "name": name,
        "built": date.today().isoformat(),
        "articles": len(manifest_items),
        "passages": len(kept),
        "subjects": sorted({i["subject"] for i in manifest_items}),
        **({"index": index_stats} if index_stats else {}),
        "content_hash": compute_content_hash(files),
    }
    (tmp / "meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")

    if with_zim:  # after meta.json (the date comes from it); the ZIM is not part of the content hash
        from pipeline.stages.package import package_zim

        package_zim(tmp)

    report = validate(load_pack(tmp))
    if not report.ok:
        return None, report  # leave the temporary directory for inspection; the previous pack is untouched
    final = out_dir / name
    if final.exists():
        shutil.rmtree(final)
    tmp.rename(final)
    return final, report


def main() -> int:
    path, report = assemble()
    print(report.format())
    print(f"pack written to {path}" if path else "validation failed; pack not replaced")
    return 0 if path else 1


if __name__ == "__main__":
    sys.exit(main())
