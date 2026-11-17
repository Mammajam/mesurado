"""Tests for the fallback SVG map (spec: map-and-timeline R2.3; content-pipeline R10.2; task 6b.2 first part)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.stages.fallback_map import (
    BBOX, DATASETS, MAX_BYTES, build_svg, clip_ring, dataset_manifest_items, fetch_dataset, make_projection, project, simplify,
)
from pipeline.validate import load_pack, validate
from tests.pipeline.packfactory import build


def square(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def feature(geom, **props):
    return {"type": "Feature", "properties": props, "geometry": geom}


def poly(*rings):
    return {"type": "Polygon", "coordinates": [[list(p) for p in r] for r in rings]}


def synthetic():
    countries = {"features": [
        feature(poly(square(-12, 4, -7, 9)), NAME_EN="Liberia", ISO_A2="LR"),
        feature(poly(square(-14, 7, -10, 11)), NAME_EN="Sierra Leone", ISO_A2="SL"),
        feature(poly(square(30, 30, 40, 40)), NAME_EN="Far Away", ISO_A2="FA"),
    ]}
    admin1 = {"features": [
        feature(poly(square(-12, 4, -9, 9)), name="Alpha", iso_a2="LR"),
        feature(poly(square(-9, 4, -7, 9)), name="Beta", iso_a2="LR"),
        feature(poly(square(-14, 7, -10, 11)), name="Elsewhere", iso_a2="SL"),
    ]}
    rivers = {"features": [feature({"type": "LineString", "coordinates": [[-11, 5], [-10, 6], [-9, 7]]}, scalerank=3)]}
    return countries, admin1, rivers


def test_projection_maps_corners_and_known_points_inside_the_viewbox():
    proj = make_projection()
    x, y = project(BBOX[0], BBOX[3], proj)
    assert (round(x), round(y)) == (0, 0)
    x, y = project(BBOX[2], BBOX[1], proj)
    assert (round(x), round(y)) == (proj["width"], proj["height"])
    mx, my = project(-10.8014, 6.3133, proj)  # Monrovia
    assert 0 < mx < proj["width"] and 0 < my < proj["height"]
    assert project(-8.0, 6.0, proj)[0] > project(-12.0, 6.0, proj)[0]  # east is right
    assert project(-10, 5.0, proj)[1] > project(-10, 8.0, proj)[1]  # north is up


def test_svg_has_layers_projection_and_only_places_inside_the_box():
    svg = build_svg(*synthetic())
    assert 'data-projection="equirectangular-cos"' in svg and 'viewBox="0 0 ' in svg and 'id="markers"' in svg
    assert "Liberia" in svg and "Sierra Leone" in svg and "Far Away" not in svg
    assert "Alpha County" in svg and "Beta County" in svg and "Elsewhere" not in svg  # counties are Liberia only
    assert "<script" not in svg and "http://" not in svg.replace("http://www.w3.org/2000/svg", "")


def test_svg_is_deterministic():
    assert build_svg(*synthetic()) == build_svg(*synthetic())


@settings(max_examples=60, deadline=None)
@given(st.lists(st.tuples(st.floats(-20, 20), st.floats(-5, 25)), min_size=3, max_size=30))
def test_clipped_rings_stay_inside_the_box(points):
    for lon, lat in clip_ring(points + [points[0]], BBOX):
        assert BBOX[0] - 1e-9 <= lon <= BBOX[2] + 1e-9 and BBOX[1] - 1e-9 <= lat <= BBOX[3] + 1e-9


@settings(max_examples=60, deadline=None)
@given(st.lists(st.tuples(st.floats(-10, 10), st.floats(-10, 10)), min_size=2, max_size=40), st.floats(0.0, 2.0))
def test_simplify_keeps_end_points_and_never_adds_points(points, tol):
    out = simplify(points, tol)
    assert out[0] == points[0] and out[-1] == points[-1]
    assert len(out) <= len(points) and all(p in points for p in out)


def test_simplify_with_zero_tolerance_keeps_every_corner():
    ring = square(0, 0, 4, 4)
    assert simplify(ring, 0.0) == ring


def test_dataset_manifest_items_record_license_and_credit():
    items = dataset_manifest_items("2026-11-17")
    assert len(items) == 3 and all(i["license"] == "PD" and i["type"] == "dataset" and i["file"] == "fallback-map.svg" for i in items)
    assert all(i["attribution"] and i["revision"] == "5.1.2" and i["source_url"].startswith("https://") for i in items)


def test_locked_hash_is_enforced(tmp_path):
    cache = tmp_path / "c"
    cache.mkdir()
    (cache / f"{DATASETS['rivers']}.geojson").write_text('{"features": []}')
    lock = tmp_path / "lock.json"
    fetch_dataset("rivers", cache, lock)  # first use records the hash
    assert json.loads(lock.read_text())["sha256"][DATASETS["rivers"]]
    (cache / f"{DATASETS['rivers']}.geojson").write_text('{"features": [1]}')
    with pytest.raises(ValueError, match="locked sha256"):
        fetch_dataset("rivers", cache, lock)


def disk_pack(tmp_path: Path, svg: str) -> Path:
    obj = build(["Some article text for the pack. " * 4])
    root = tmp_path / "p"
    for rel, data in obj.files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data if isinstance(data, bytes) else data.read_bytes())
    (root / "fallback-map.svg").write_text(svg, encoding="utf-8")
    return root


def codes(root: Path) -> set[str]:
    return validate(load_pack(root)).error_codes() - {"META_HASH_MISMATCH"}


def test_validator_accepts_a_good_map_and_rejects_bad_ones(tmp_path):
    good = build_svg(*synthetic())
    assert codes(disk_pack(tmp_path / "a", good)) == set()
    assert "FALLBACK_MAP_INVALID" in codes(disk_pack(tmp_path / "b", "<html>not a map</html>"))
    assert "FALLBACK_MAP_INVALID" in codes(disk_pack(tmp_path / "c", re.sub(r' data-bbox="[^"]*"', "", good)))
    assert "FALLBACK_MAP_INVALID" in codes(disk_pack(tmp_path / "d", good.replace('id="markers"', 'id="m"')))
    assert "FALLBACK_MAP_UNSAFE" in codes(disk_pack(tmp_path / "e", good.replace("</svg>", "<script>alert(1)</script></svg>")))
    assert "FALLBACK_MAP_TOO_LARGE" in codes(disk_pack(tmp_path / "f", good + " " * (MAX_BYTES + 10)))
