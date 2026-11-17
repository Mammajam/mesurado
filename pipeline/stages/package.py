"""Package stage: write the ZIM container for an unpacked pack (spec: content-pipeline R5.1).

mesurado.zim holds every article text file under the same path as in the pack directory
(articles/<slug>.txt, text/plain, the exact bytes the passage offsets point into) plus ZIM metadata
(title, license, creator, date). Passages, indexes and the manifest stay as separate files next to it.
Images join the ZIM in task 3.2.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from libzim.writer import Creator, Hint, Item, StringProvider

ZIM_NAME = "mesurado.zim"


class _TextItem(Item):
    def __init__(self, path: str, title: str, data: bytes):
        super().__init__()
        self._path, self._title, self._data = path, title, data

    def get_path(self) -> str:
        return self._path

    def get_title(self) -> str:
        return self._title

    def get_mimetype(self) -> str:
        return "text/plain; charset=utf-8"

    def get_contentprovider(self) -> StringProvider:
        return StringProvider(self._data.decode("utf-8"))

    def get_hints(self) -> dict:
        return {Hint.FRONT_ARTICLE: True, Hint.COMPRESS: True}


def package_zim(pack: Path, date: str | None = None) -> Path:
    """Write pack/mesurado.zim from the manifest and article files. Returns its path."""
    items = [i for i in json.loads((pack / "manifest.json").read_text(encoding="utf-8"))["items"] if i.get("type") == "article"]
    meta = json.loads((pack / "meta.json").read_text(encoding="utf-8")) if (pack / "meta.json").exists() else {}
    out = pack / ZIM_NAME
    if out.exists():
        out.unlink()
    with Creator(out).config_indexing(False, "en").config_compression("zstd").set_mainpath(items[0]["text_file"]) as zim:
        for key, value in {
            "Title": "Mesurado learning pack", "Description": "Curated, cited learning articles (history and geography)",
            "Language": "eng", "Creator": "Wikipedia contributors", "Publisher": "Mesurado",
            "Date": date or meta.get("built", "1970-01-01"), "License": "CC-BY-SA-4.0",
            "Name": meta.get("name", "mesurado"), "Tags": "_category:history;_category:geography",
        }.items():
            zim.add_metadata(key, value)
        for item in items:
            ref = item["text_file"]
            zim.add_item(_TextItem(ref, item["title"], (pack / ref).read_bytes()))
    return out


def main(argv: list[str]) -> int:
    from pipeline.stages.assemble import OUT_DIR

    pack = Path(argv[0]) if argv else OUT_DIR / "dev"
    out = package_zim(pack)
    print(f"{out} ({out.stat().st_size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
