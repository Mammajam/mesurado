"""Attribution stage: credit text for every item and an attribution file (spec: content-pipeline R7).

attribution.json  machine-readable: pack license plus one entry per manifest item with the credit text the app
                  shows on the article page, the source and history links, the license and its URL.
attribution.md    the same as a readable list, for the repository, the demo and anyone opening the pack folder.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PACK_LICENSE = "CC-BY-SA-4.0"
LICENSE_URLS = {
    "CC-BY-SA-4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC-BY-SA-3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC-BY-3.0": "https://creativecommons.org/licenses/by/3.0/",
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "ODbL-1.0": "https://opendatacommons.org/licenses/odbl/1-0/",
    "OFL-1.1": "https://openfontlicense.org/open-font-license-official-text/",
    "PD": "https://creativecommons.org/publicdomain/mark/1.0/",
}
SPDX_NAMES = {k: k.replace("CC-BY-SA-", "CC BY-SA ").replace("CC-BY-", "CC BY ").replace("CC0-1.0", "CC0 1.0") for k in LICENSE_URLS}
SPDX_NAMES["PD"] = "Public domain (PD)"


def license_name(spdx: str) -> str:
    return SPDX_NAMES.get(spdx, spdx)


def credit_text(item: dict[str, Any]) -> str:
    """One sentence the app shows under an article: what it is, who made it, which version, which license, what we changed."""
    who = str(item.get("attribution", "")).strip()
    mods = ", ".join(item.get("modifications", [])) or "none"
    return (
        f"“{item['title']}” by {who}, revision {item['revision']} (retrieved {item['retrieved_at']}), "
        f"licensed under {license_name(item['license'])}. Changes: {mods}."
    )


def build_attribution(items: list[dict[str, Any]], pack_name: str = "Mesurado learning pack") -> dict[str, Any]:
    entries = []
    for item in sorted(items, key=lambda i: str(i["id"])):
        entries.append({
            "id": item["id"], "type": item.get("type", "article"), "title": item["title"], "credit": credit_text(item),
            "attribution": item["attribution"], "source_url": item["source_url"], "history_url": item.get("history_url", ""),
            "license": item["license"], "license_url": LICENSE_URLS.get(item["license"], ""),
            "revision": item["revision"], "retrieved_at": item["retrieved_at"], "modifications": item.get("modifications", []),
        })
    return {
        "format": "mesurado-attribution-1",
        "pack": pack_name,
        "pack_license": PACK_LICENSE,
        "pack_license_url": LICENSE_URLS[PACK_LICENSE],
        "notice": "This pack is distributed under CC BY-SA. Articles are adapted from Wikipedia; each item below lists its "
                  "authors (via the history link), license and the changes made.",
        "items": entries,
    }


def render_markdown(att: dict[str, Any]) -> str:
    lines = [f"# Attribution: {att['pack']}", "", att["notice"], "",
             f"Pack license: [{license_name(att['pack_license'])}]({att['pack_license_url']})", "",
             f"{len(att['items'])} items.", ""]
    for e in att["items"]:
        links = f"[source]({e['source_url']})"
        if e["history_url"]:
            links += f", [authors]({e['history_url']})"
        if e["license_url"]:
            links += f", [license]({e['license_url']})"
        lines.append(f"- **{e['title']}** ({e['id']}): {e['credit']} {links}")
    return "\n".join(lines) + "\n"


def write_attribution(pack: Path) -> dict[str, Any]:
    items = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))["items"]
    att = build_attribution(items)
    (pack / "attribution.json").write_text(json.dumps(att, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (pack / "attribution.md").write_text(render_markdown(att), encoding="utf-8")
    return att


def main(argv: list[str]) -> int:
    from pipeline.stages.assemble import OUT_DIR

    pack = Path(argv[0]) if argv else OUT_DIR / "dev"
    att = write_attribution(pack)
    print(f"attribution for {len(att['items'])} items written to {pack}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
