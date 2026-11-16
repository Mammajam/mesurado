"""CLI: python -m pipeline.validate <pack-dir> [--json]. Exits 1 on any error (spec R6.5)."""

from __future__ import annotations

import argparse
import json
import sys

from . import validate_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pipeline.validate", description="Validate a Mesurado pack directory.")
    ap.add_argument("pack", help="path to an unpacked pack directory")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ns = ap.parse_args(argv)
    report = validate_path(ns.pack)
    print(json.dumps(report.as_dict(), indent=2) if ns.json else report.format())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
