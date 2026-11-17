"""Fallback map stage: a small SVG map of West Africa with Liberia's counties (spec: map-and-timeline R2.3).

Data: Natural Earth v5.1.2 (public domain): 50m countries, 10m first-level divisions (Liberia only), 50m rivers.
The source files are downloaded once into pipeline/cache/naturalearth/ and checked against the sha256 values in
pipeline/naturalearth.lock.json, so a rebuild uses the same data. The SVG uses an equirectangular projection scaled by
cos(centre latitude); the projection is written into the root element (data-* attributes) so the app can place markers
with `project()` below, ported to JavaScript and tested against the same values.

Layers (SVG groups): #countries, #counties, #rivers, #labels, and an empty #markers group for the app.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import urllib.request
from pathlib import Path
from typing import Any, Iterable

CACHE_DIR = Path(__file__).resolve().parents[1] / "cache" / "naturalearth"
LOCK_FILE = Path(__file__).resolve().parents[1] / "naturalearth.lock.json"
VERSION = "5.1.2"
BASE_URL = f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v{VERSION}/geojson/"
USER_AGENT = "mesurado-pipeline/0.1 (open-source offline learning pack; MIT; polite batch client)"
DATASETS = {
    "countries": "ne_50m_admin_0_countries",
    "admin1": "ne_10m_admin_1_states_provinces",
    "rivers": "ne_50m_rivers_lake_centerlines",
}
# West Africa: Senegal to Nigeria, Mali's south to the Gulf of Guinea (degrees).
BBOX = (-18.0, 3.5, 15.5, 18.0)  # min_lon, min_lat, max_lon, max_lat
SCALE = 100  # SVG units per degree of latitude
COUNTRY_TOLERANCE = 0.03  # degrees, Douglas-Peucker
COUNTY_TOLERANCE = 0.006
RIVER_TOLERANCE = 0.04
MAX_BYTES = 400_000  # map-and-timeline budget for the fallback map
LABELLED = {"Liberia", "Sierra Leone", "Guinea", "Ivory Coast", "Ghana", "Mali", "Nigeria", "Senegal", "Burkina Faso", "Togo", "Benin", "Niger"}


# ---- data ----------------------------------------------------------------------------------


def fetch_dataset(key: str, cache: Path = CACHE_DIR, lock_file: Path = LOCK_FILE) -> Path:
    """Download (once) and verify one Natural Earth file. Records the hash in the lock file on first download."""
    name = DATASETS[key]
    path = cache / f"{name}.geojson"
    cache.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        req = urllib.request.Request(BASE_URL + f"{name}.geojson", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 (fixed https URL)
            path.write_bytes(r.read())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    lock = json.loads(lock_file.read_text(encoding="utf-8")) if lock_file.exists() else {"version": VERSION, "sha256": {}}
    known = lock["sha256"].get(name)
    if known is None:
        lock["sha256"][name] = digest
        lock_file.write_text(json.dumps(lock, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    elif known != digest:
        raise ValueError(f"{path.name} does not match the locked sha256 (expected {known[:12]}..., got {digest[:12]}...)")
    return path


# ---- geometry ------------------------------------------------------------------------------

Point = tuple[float, float]


def make_projection(bbox: tuple[float, float, float, float] = BBOX, scale: float = SCALE) -> dict[str, Any]:
    min_lon, min_lat, max_lon, max_lat = bbox
    k = math.cos(math.radians((min_lat + max_lat) / 2))
    return {"type": "equirectangular-cos", "bbox": list(bbox), "scale": scale, "k": round(k, 6),
            "width": round((max_lon - min_lon) * k * scale), "height": round((max_lat - min_lat) * scale)}


def project(lon: float, lat: float, proj: dict[str, Any]) -> Point:
    """SVG (x, y) for a longitude and latitude. The app uses the same formula for markers."""
    min_lon, min_lat, _, max_lat = proj["bbox"]
    return ((lon - min_lon) * proj["k"] * proj["scale"], (max_lat - lat) * proj["scale"])


def simplify(points: list[Point], tolerance: float) -> list[Point]:
    """Douglas-Peucker (iterative). Keeps the end points; a closed ring keeps at least 4 points."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = points[a], points[b]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        far, far_i = 0.0, -1
        for i in range(a + 1, b):
            x, y = points[i]
            d = abs(dy * (x - x1) - dx * (y - y1)) / norm if norm else math.hypot(x - x1, y - y1)
            if d > far:
                far, far_i = d, i
        if far > tolerance and far_i > 0:
            keep[far_i] = True
            stack += [(a, far_i), (far_i, b)]
    out = [p for p, k in zip(points, keep) if k]
    return out if len(out) >= 4 or len(points) < 4 else points[:3] + points[-1:]


def clip_ring(ring: list[Point], bbox: tuple[float, float, float, float]) -> list[Point]:
    """Sutherland-Hodgman clip of a polygon ring to the bounding box (so shapes stop at the map edge)."""
    min_lon, min_lat, max_lon, max_lat = bbox
    edges = [
        (lambda p: p[0] >= min_lon, lambda a, b: (min_lon, a[1] + (b[1] - a[1]) * (min_lon - a[0]) / (b[0] - a[0]))),
        (lambda p: p[0] <= max_lon, lambda a, b: (max_lon, a[1] + (b[1] - a[1]) * (max_lon - a[0]) / (b[0] - a[0]))),
        (lambda p: p[1] >= min_lat, lambda a, b: (a[0] + (b[0] - a[0]) * (min_lat - a[1]) / (b[1] - a[1]), min_lat)),
        (lambda p: p[1] <= max_lat, lambda a, b: (a[0] + (b[0] - a[0]) * (max_lat - a[1]) / (b[1] - a[1]), max_lat)),
    ]
    pts = ring[:-1] if ring and ring[0] == ring[-1] else list(ring)
    for inside, cut in edges:
        if not pts:
            break
        out: list[Point] = []
        prev = pts[-1]
        for cur in pts:
            if inside(cur):
                if not inside(prev):
                    out.append(cut(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cut(prev, cur))
            prev = cur
        pts = out
    return pts + [pts[0]] if len(pts) >= 3 else []


def clip_line(line: list[Point], bbox: tuple[float, float, float, float]) -> list[list[Point]]:
    """Keep the parts of a polyline whose vertices lie inside the box (rivers: no need for exact edge cuts)."""
    min_lon, min_lat, max_lon, max_lat = bbox
    parts: list[list[Point]] = []
    cur: list[Point] = []
    for p in line:
        if min_lon <= p[0] <= max_lon and min_lat <= p[1] <= max_lat:
            cur.append(p)
        else:
            if len(cur) > 1:
                parts.append(cur)
            cur = []
    if len(cur) > 1:
        parts.append(cur)
    return parts


def _rings(geom: dict[str, Any]) -> Iterable[list[Point]]:
    """Outer and inner rings of a (Multi)Polygon as lists of (lon, lat)."""
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]] if geom["type"] == "Polygon" else []
    for poly in polys:
        for ring in poly:
            yield [(float(x), float(y)) for x, y, *_ in ring]


def ring_path(ring: list[Point], proj: dict[str, Any], tolerance: float, bbox=BBOX) -> str:
    clipped = clip_ring(ring, bbox)
    if not clipped:
        return ""
    pts = simplify(clipped, tolerance)
    xy = [project(lon, lat, proj) for lon, lat in pts]
    if len(xy) < 4:
        return ""
    return _path(xy, close=True)


def _path(xy: list[Point], close: bool) -> str:
    """'M x y l dx dy ...' with integer coordinates (relative moves after the first point)."""
    pts = [(round(x), round(y)) for x, y in xy]
    out = [f"M{pts[0][0]} {pts[0][1]}"]
    px, py = pts[0]
    deltas = []
    for x, y in pts[1:-1] if close else pts[1:]:
        if (x, y) != (px, py):
            deltas.append(f"{x - px} {y - py}")
            px, py = x, y
    if deltas:
        out.append("l" + " ".join(deltas))
    return "".join(out) + ("z" if close else "")


def _intersects(geom: dict[str, Any], bbox) -> bool:
    for ring in _rings(geom):
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        if max(xs) >= bbox[0] and min(xs) <= bbox[2] and max(ys) >= bbox[1] and min(ys) <= bbox[3]:
            return True
    return False


def _centroid(geom: dict[str, Any]) -> Point:
    """Centre of the largest ring's bounding box (good enough for a label anchor)."""
    ring = max(_rings(geom), key=lambda r: (max(p[0] for p in r) - min(p[0] for p in r)) * (max(p[1] for p in r) - min(p[1] for p in r)))
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ---- SVG -----------------------------------------------------------------------------------

STYLE = """
:root{--sea:#dbe9f3;--land:#f1ece0;--liberia:#e3d9bd;--line:#8a8574;--county:#a39a7c;--river:#7fa6c4;--label:#3d3a30}
@media (prefers-color-scheme:dark){:root{--sea:#14232e;--land:#2a2a25;--liberia:#3a3829;--line:#6b6858;--county:#5f5b47;--river:#3f6a8a;--label:#d8d3c4}}
.sea{fill:var(--sea)}.country{fill:var(--land);stroke:var(--line);stroke-width:2}.liberia{fill:var(--liberia)}
.county{fill:none;stroke:var(--county);stroke-width:1.2}.river{fill:none;stroke:var(--river);stroke-width:1.5}
.label{fill:var(--label);font:600 22px sans-serif;text-anchor:middle}.county-label{font-size:12px;font-weight:400}
""".strip()


def build_svg(countries: dict, admin1: dict, rivers: dict, bbox=BBOX) -> str:
    proj = make_projection(bbox)
    country_paths, labels = [], []
    for f in sorted(countries["features"], key=lambda f: f["properties"]["NAME_EN"]):
        if not _intersects(f["geometry"], bbox):
            continue
        name = f["properties"]["NAME_EN"]
        d = "".join(ring_path(r, proj, COUNTRY_TOLERANCE, bbox) for r in _rings(f["geometry"]))
        if not d:
            continue
        cls = "country liberia" if name == "Liberia" else "country"
        country_paths.append(f'<path class="{cls}" id="c-{_esc(f["properties"]["ISO_A2"] or name)}" data-name="{_esc(name)}" d="{d}"><title>{_esc(name)}</title></path>')
        if name in LABELLED:
            lon, lat = _centroid(f["geometry"])
            if bbox[0] < lon < bbox[2] and bbox[1] < lat < bbox[3]:
                x, y = project(lon, lat, proj)
                labels.append(f'<text class="label" x="{round(x)}" y="{round(y)}">{_esc(name)}</text>')
    county_paths = []
    for f in sorted((f for f in admin1["features"] if f["properties"].get("iso_a2") == "LR"), key=lambda f: f["properties"]["name"]):
        name = f["properties"]["name"]
        d = "".join(ring_path(r, proj, COUNTY_TOLERANCE, bbox) for r in _rings(f["geometry"]))
        county_paths.append(f'<path class="county" data-name="{_esc(name)} County" d="{d}"><title>{_esc(name)} County</title></path>')
        lon, lat = _centroid(f["geometry"])
        x, y = project(lon, lat, proj)
        labels.append(f'<text class="label county-label" x="{round(x)}" y="{round(y)}">{_esc(name)}</text>')
    river_paths = []
    for f in rivers["features"]:
        g = f["geometry"]
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]] if g["type"] == "LineString" else []
        for line in lines:
            for part in clip_line([(float(x), float(y)) for x, y, *_ in line], bbox):
                xy = [project(lon, lat, proj) for lon, lat in simplify(part, RIVER_TOLERANCE)]
                if len(xy) > 1 and f["properties"].get("scalerank", 9) <= 6:
                    river_paths.append(f'<path class="river" d="{_path(xy, close=False)}"/>')
    attrs = (f'data-projection="{proj["type"]}" data-bbox="{",".join(str(v) for v in proj["bbox"])}" data-scale="{proj["scale"]}" '
             f'data-k="{proj["k"]}"')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {proj["width"]} {proj["height"]}" role="img" '
        f'aria-labelledby="map-title map-desc" {attrs}>\n'
        f'<title id="map-title">Map of West Africa with the counties of Liberia</title>\n'
        f'<desc id="map-desc">Simple offline map. Map data: Natural Earth (public domain), version {VERSION}. Borders are shown as in Natural Earth and make no claim on disputed areas.</desc>\n'
        f'<style>{STYLE}</style>\n<rect class="sea" width="{proj["width"]}" height="{proj["height"]}"/>\n'
        f'<g id="countries">\n' + "\n".join(country_paths) + '\n</g>\n'
        f'<g id="rivers">\n' + "\n".join(river_paths) + '\n</g>\n'
        f'<g id="counties">\n' + "\n".join(county_paths) + '\n</g>\n'
        f'<g id="labels">\n' + "\n".join(labels) + '\n</g>\n'
        f'<g id="markers"></g>\n</svg>\n'
    )


DATASET_ITEMS = [
    {"id": "ne:admin_0_countries", "type": "dataset", "title": "Natural Earth admin 0 countries (1:50m)"},
    {"id": "ne:admin_1_states_provinces", "type": "dataset", "title": "Natural Earth admin 1 states and provinces (1:10m), Liberia counties"},
    {"id": "ne:rivers_lake_centerlines", "type": "dataset", "title": "Natural Earth rivers and lake centerlines (1:50m)"},
]


def dataset_manifest_items(retrieved_at: str) -> list[dict[str, Any]]:
    """Manifest entries for the source datasets (license and attribution recorded, R10.2). `file` points at the SVG."""
    return [{
        **d, "subject": "geography", "source_url": "https://www.naturalearthdata.com/", "revision": VERSION, "license": "PD",
        "attribution": "Natural Earth (naturalearthdata.com), public domain",
        "retrieved_at": retrieved_at, "modifications": ["clipped to West Africa", "simplified", "projected to SVG"],
        "file": "fallback-map.svg",
    } for d in DATASET_ITEMS]


def write_fallback_map(pack: Path, cache: Path = CACHE_DIR) -> int:
    data = {k: json.loads(fetch_dataset(k, cache).read_text(encoding="utf-8")) for k in DATASETS}
    svg = build_svg(data["countries"], data["admin1"], data["rivers"])
    (pack / "fallback-map.svg").write_text(svg, encoding="utf-8")
    return len(svg.encode("utf-8"))


def main(argv: list[str]) -> int:
    from pipeline.stages.assemble import OUT_DIR

    pack = Path(argv[0]) if argv else OUT_DIR / "dev"
    size = write_fallback_map(pack)
    print(f"fallback-map.svg {size / 1000:.0f} KB (budget {MAX_BYTES // 1000} KB)")
    return 0 if size <= MAX_BYTES else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
