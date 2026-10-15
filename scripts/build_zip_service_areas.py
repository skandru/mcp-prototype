"""Build the ZIP -> public water system lookup from service-area polygons.

Downloads two public layers and intersects them offline, writing
datasets/drinking_water/zip_service_areas.csv (one row per ZIP x system whose
service area overlaps that ZIP):

  - State Water Board "System Area Boundary Layer" (ArcGIS FeatureServer)
  - CA ZIP Code Boundaries (gis.data.ca.gov GeoJSON, cached locally)

Requires shapely (`pip install shapely`); everything else is standard library.

    python scripts/build_zip_service_areas.py

Columns: zip, pws_id, system_name, overlap_sq_km, pct_of_zip_covered (share of
the ZIP's area inside the service area), pct_of_system_in_zip. Areas use a
local equirectangular approximation, which is accurate to a few percent for
California-sized shapes; it is used for ranking, not surveying.
"""

from __future__ import annotations

import csv
import json
import math
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import shapely
from shapely import STRtree
from shapely.geometry import shape
from shapely.validation import make_valid

OUT_DIR = Path(__file__).resolve().parent.parent / "datasets" / "drinking_water"
SABL = (
    "https://gispublic.waterboards.ca.gov/portalserver/rest/services/"
    "Drinking_Water/California_Drinking_Water_System_Area_Boundaries/"
    "FeatureServer/0/query"
)
ZIP_URL = (
    "https://gis.data.ca.gov/api/download/v1/items/"
    "f7afe55481244706903fbe6be5e986d3/geojson?layers=0"
)
PAGE = 250
KM_PER_DEG = 111.32
MIN_PCT = 0.5  # drop slivers covering under 0.5% of both the ZIP and the system


def _get(url: str, timeout: int = 300) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "dw-zip-builder"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_service_areas() -> list[dict]:
    features: list[dict] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode(
            {
                "where": "1=1",
                "outFields": "WATER_SYSTEM_NUMBER,WATER_SYSTEM_NAME",
                "outSR": 4326,
                "f": "geojson",
                "resultOffset": offset,
                "resultRecordCount": PAGE,
                "orderByFields": "OBJECTID",
            }
        )
        page = json.loads(_get(f"{SABL}?{query}"))
        batch = page.get("features", [])
        features.extend(batch)
        print(f"  service areas: {len(features)}", file=sys.stderr)
        if len(batch) < PAGE and not page.get("exceededTransferLimit"):
            return features
        offset += len(batch)


def load_zip_features() -> list[dict]:
    cache = OUT_DIR / "ca_zip_boundaries.geojson"
    if not cache.exists():
        print("Downloading CA ZIP boundaries (~120 MB)...", file=sys.stderr)
        cache.write_bytes(_get(ZIP_URL, timeout=900))
    return json.loads(cache.read_text(encoding="utf-8"))["features"]


def _zip_of(props: dict) -> str | None:
    for key in ("ZIP_CODE", "ZIP", "ZCTA5CE20", "GEOID"):
        value = props.get(key)
        if value:
            return str(value).strip().zfill(5)[:5]
    return None


def _flatten(geom, mercator: bool = False):
    """Project to local km around California's mean latitude (4326 or 3857)."""
    scale = math.cos(math.radians(37.0))
    radius = 6378137.0

    def convert(coords):
        x, y = coords[:, 0], coords[:, 1]
        if mercator:
            x = np.degrees(x / radius)
            y = np.degrees(2 * np.arctan(np.exp(y / radius)) - math.pi / 2)
        return np.column_stack((x * KM_PER_DEG * scale, y * KM_PER_DEG))

    return shapely.transform(geom, convert)


def _clean(geometry: dict, mercator: bool = False):
    geom = shape(geometry)
    if not geom.is_valid:
        geom = make_valid(geom)
    return _flatten(geom, mercator)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Fetching service-area boundaries...", file=sys.stderr)
    systems = []
    for feat in fetch_service_areas():
        if not feat.get("geometry"):
            continue
        props = feat["properties"]
        pws = (props.get("WATER_SYSTEM_NUMBER") or "").strip().upper()
        if pws:
            name = (props.get("WATER_SYSTEM_NAME") or "").strip()
            systems.append((pws, name, _clean(feat["geometry"])))

    tree = STRtree([g for _, _, g in systems])
    rows = []
    zips = load_zip_features()
    for i, feat in enumerate(zips, 1):
        code = _zip_of(feat["properties"])
        if not code or not feat.get("geometry"):
            continue
        zgeom = _clean(feat["geometry"], mercator=True)
        zarea = zgeom.area
        if zarea <= 0:
            continue
        for idx in tree.query(zgeom, predicate="intersects"):
            pws, name, sgeom = systems[idx]
            overlap = zgeom.intersection(sgeom).area
            if overlap <= 0 or sgeom.area <= 0:
                continue
            pct_zip = 100 * overlap / zarea
            pct_sys = 100 * overlap / sgeom.area
            if max(pct_zip, pct_sys) < MIN_PCT:
                continue
            rows.append(
                (
                    code,
                    pws,
                    name,
                    round(overlap, 4),
                    round(pct_zip, 2),
                    round(pct_sys, 2),
                )
            )
        if i % 200 == 0:
            print(f"  zips: {i}/{len(zips)}", file=sys.stderr)

    out = OUT_DIR / "zip_service_areas.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "zip",
                "pws_id",
                "system_name",
                "overlap_sq_km",
                "pct_of_zip_covered",
                "pct_of_system_in_zip",
            ]
        )
        writer.writerows(sorted(rows))
    print(f"Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
