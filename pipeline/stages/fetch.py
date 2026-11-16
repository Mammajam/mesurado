"""Fetch stage: download selected Wikipedia articles at pinned revisions (spec: content-pipeline R1, R2, R8.1, R10.1).

Two steps, so rebuilds are reproducible:
 1. Resolve each selected title to a revision id, page id, resolved title and coordinates. The result is
    written to pipeline/pins.json (committed). A title that is already pinned is never re-resolved.
 2. Download the rendered HTML of that exact revision (`action=parse&oldid=`) into pipeline/cache/ and
    write a work file plus a manifest entry per article under pipeline/work/fetch/.

Only the public MediaWiki API is used. No personal data is sent; the User-Agent is a generic project name.
Run: uv run python -m pipeline.stages.fetch [--subjects history,geography] [--limit N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from pipeline.selection import SelectedArticle, Selection, load_selection

PIPELINE_DIR = Path(__file__).resolve().parents[1]
PINS_PATH = PIPELINE_DIR / "pins.json"
CACHE_DIR = PIPELINE_DIR / "cache" / "wikipedia"
WORK_DIR = PIPELINE_DIR / "work" / "fetch"
API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "mesurado-pipeline/0.1 (open-source offline learning pack; MIT; polite batch client)"
BATCH = 50
DELAY_SECONDS = 0.6

HttpGet = Callable[[dict[str, str]], dict[str, Any]]


class FetchError(RuntimeError):
    pass


def default_http_get(params: dict[str, str]) -> dict[str, Any]:
    """GET the MediaWiki API with retries and a polite User-Agent."""
    query = urllib.parse.urlencode({**params, "format": "json", "formatversion": "2", "maxlag": "5"})
    req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
    last: Exception | None = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                if data["error"].get("code") == "maxlag":
                    time.sleep(2 * (attempt + 1))
                    continue
                raise FetchError(f"API error: {data['error']}")
            time.sleep(DELAY_SECONDS)
            return data
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (429, 503):  # rate limited: honour Retry-After, else back off for longer each time
                retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
                time.sleep(min(int(retry_after), 120) if retry_after.isdigit() else 15 * (attempt + 1))
            else:
                time.sleep(2 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise FetchError(f"request failed after retries: {last}")


def article_id(resolved_title: str) -> str:
    return "wp:" + resolved_title.replace(" ", "_")


def slug(aid: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", aid.removeprefix("wp:"))[:60]
    return f"{safe}-{hashlib.sha1(aid.encode()).hexdigest()[:6]}"


# Step 1: resolve and pin -------------------------------------------------------------------


def _chunks(seq: list[Any], n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def resolve_titles(titles: list[str], http_get: HttpGet) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return ({requested title: pin}, [problems]). A pin has revid, pageid, title, coordinates."""
    pins: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    for batch in _chunks(titles, BATCH):
        data = http_get(
            {
                "action": "query",
                "titles": "|".join(batch),
                "redirects": "1",
                "prop": "revisions|coordinates|pageprops",
                "rvprop": "ids|timestamp",
                "colimit": "max",
                "coprimary": "primary",
                "ppprop": "disambiguation",
            }
        )
        q = data.get("query", {})
        # Map each requested title through normalization and redirects to the final page title.
        forward: dict[str, str] = {t: t for t in batch}
        for hop in ("normalized", "redirects"):
            for m in q.get(hop, []):
                for k, v in list(forward.items()):
                    if v == m["from"]:
                        forward[k] = m["to"]
        by_title = {p["title"]: p for p in q.get("pages", [])}
        for requested in batch:
            page = by_title.get(forward[requested])
            if page is None or page.get("missing"):
                problems.append(f"{requested}: page not found")
                continue
            if "disambiguation" in page.get("pageprops", {}):
                problems.append(f"{requested}: is a disambiguation page")
                continue
            revs = page.get("revisions") or []
            if not revs:
                problems.append(f"{requested}: no revision returned")
                continue
            coords = None
            for c in page.get("coordinates", []) or []:
                if c.get("globe", "earth") == "earth" and c.get("primary", True):
                    coords = {"lat": c["lat"], "lon": c["lon"], "precision": "page"}
                    break
            pins[requested] = {
                "title": page["title"],
                "pageid": page["pageid"],
                "revid": revs[0]["revid"],
                "revision_time": revs[0].get("timestamp"),
                "coordinates": coords,
            }
    return pins, problems


def load_pins(path: Path = PINS_PATH) -> dict[str, dict[str, Any]]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_pins(pins: dict[str, dict[str, Any]], path: Path = PINS_PATH) -> None:
    path.write_text(json.dumps(pins, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


# Step 2: download pinned revisions ---------------------------------------------------------


def download_revision(revid: int, http_get: HttpGet, cache_dir: Path = CACHE_DIR) -> dict[str, Any]:
    """Return {'retrieved_at', 'html', 'title'} for a revision, using the cache when present."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    f = cache_dir / f"{revid}.json"
    if f.is_file():
        return json.loads(f.read_text(encoding="utf-8"))
    data = http_get({"action": "parse", "oldid": str(revid), "prop": "text|displaytitle", "disableeditsection": "1", "disablelimitreport": "1"})
    parsed = data.get("parse")
    if not parsed or "text" not in parsed:
        raise FetchError(f"revision {revid}: no parse result")
    rec = {"retrieved_at": date.today().isoformat(), "title": parsed.get("title", ""), "html": parsed["text"]}
    f.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return rec


def manifest_entry(sel: SelectedArticle, pin: dict[str, Any], retrieved_at: str, license_id: str = "CC-BY-SA-4.0") -> dict[str, Any]:
    title = pin["title"]
    quoted = urllib.parse.quote(title.replace(" ", "_"))
    entry: dict[str, Any] = {
        "id": article_id(title),
        "type": "article",
        "title": title,
        "subject": sel.subject,
        "source_url": f"https://en.wikipedia.org/w/index.php?title={quoted}&oldid={pin['revid']}",
        "history_url": f"https://en.wikipedia.org/w/index.php?title={quoted}&action=history",
        "revision": str(pin["revid"]),
        "license": license_id,
        "attribution": "Wikipedia contributors; authors are listed in the page history",
        "retrieved_at": retrieved_at,
        "modifications": ["cleaned", "split into passages"],
    }
    if pin.get("coordinates"):
        entry["coordinates"] = pin["coordinates"]
    return entry


@dataclass
class FetchResult:
    items: list[dict[str, Any]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    new_pins: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems


def fetch(
    selection: Selection,
    subjects: list[str] | None = None,
    limit: int | None = None,
    http_get: HttpGet = default_http_get,
    pins_path: Path = PINS_PATH,
    cache_dir: Path = CACHE_DIR,
    work_dir: Path = WORK_DIR,
    log: Callable[[str], None] = lambda s: None,
) -> FetchResult:
    chosen = selection.articles(subjects)
    if limit:
        chosen = chosen[:limit]
    result = FetchResult()
    pins = load_pins(pins_path)
    todo = [a.title for a in chosen if a.title not in pins]
    if todo:
        log(f"resolving {len(todo)} titles")
        new, problems = resolve_titles(todo, http_get)
        pins.update(new)
        result.new_pins = len(new)
        result.problems.extend(problems)
        save_pins(pins, pins_path)

    work_dir.mkdir(parents=True, exist_ok=True)
    seen_ids: dict[str, str] = {}
    for n, sel in enumerate(chosen, start=1):
        pin = pins.get(sel.title)
        if pin is None:
            continue  # already reported as a problem
        aid = article_id(pin["title"])
        if aid in seen_ids:
            result.problems.append(f"{sel.title}: resolves to {pin['title']}, already selected as `{seen_ids[aid]}`")
            continue
        seen_ids[aid] = sel.title
        try:
            rec = download_revision(pin["revid"], http_get, cache_dir)
        except FetchError as exc:
            result.problems.append(f"{sel.title}: {exc}")
            continue
        entry = manifest_entry(sel, pin, rec["retrieved_at"], "CC-BY-SA-4.0")
        sdir = work_dir / sel.subject
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / f"{slug(aid)}.json").write_text(json.dumps({**entry, "html": rec["html"]}, ensure_ascii=False), encoding="utf-8")
        result.items.append(entry)
        log(f"[{n}/{len(chosen)}] {aid} r{pin['revid']}")
    (work_dir / "items.json").write_text(json.dumps({"items": result.items}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pipeline.stages.fetch")
    ap.add_argument("--subjects", help="comma-separated subjects (default: all)")
    ap.add_argument("--limit", type=int, help="fetch only the first N selected articles (for trials)")
    ns = ap.parse_args(argv)
    sel = load_selection()
    res = fetch(sel, ns.subjects.split(",") if ns.subjects else None, ns.limit, log=lambda s: print(s, flush=True))
    print(f"fetched {len(res.items)} articles, {res.new_pins} new pins, {len(res.problems)} problems")
    for p in res.problems:
        print("  PROBLEM", p)
    return 0 if res.ok else 1


if __name__ == "__main__":
    sys.exit(main())
