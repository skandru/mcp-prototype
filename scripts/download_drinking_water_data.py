"""Download California drinking-water open data from data.ca.gov into ./datasets.

Standard library only; no API key is needed. Download URLs are resolved at run
time through the CKAN `resource_show` API because some are short-lived signed
links.

    python scripts/download_drinking_water_data.py                 # core set
    python scripts/download_drinking_water_data.py --list          # show datasets
    python scripts/download_drinking_water_data.py --only safer lead_schools
    python scripts/download_drinking_water_data.py --skip-large    # < 500 MB only
    python scripts/download_drinking_water_data.py --with-pfas     # add PFAS

Files land in datasets/drinking_water/ with a manifest.json (rows, bytes, and
newest sample date). Datasets with a date column are filtered to --min-year
while streaming; snapshot datasets (systems, SAFER) are kept whole.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CKAN = "https://data.ca.gov/api/3/action"
OUT_DIR = Path(__file__).resolve().parent.parent / "datasets" / "drinking_water"
LARGE_BYTES = 500_000_000
CHUNK = 1 << 20

csv.field_size_limit(1 << 24)


@dataclass(frozen=True)
class Dataset:
    key: str
    filename: str
    resource_id: str
    description: str
    # Column holding the sample date (ISO year first); None = keep every row.
    date_column: str | None = None
    # Already limited to 2020 onward at the source, so no row filtering needed.
    prefiltered: bool = False
    optional: bool = False


DATASETS = [
    Dataset(
        "pws_systems",
        "pws_systems.csv",
        "5af27515-f0da-4cc9-92c5-0cd8eeee6843",
        "Public water systems (SDWIS): name, type, county, city, population",
    ),
    Dataset(
        "safer",
        "safer_risk_assessment.csv",
        "255887bb-5451-4c19-8e35-27899ae8c3ad",
        "SAFER failing/at-risk systems: ZIP, lat/long, MCL violations, risk scores",
    ),
    Dataset(
        "lead_schools",
        "lead_schools.csv",
        "5ebb2d68-1186-4937-acaf-8564c9a01ed6",
        "Lead sampling results at California K-12 schools",
        date_column="sample_date",
    ),
    Dataset(
        "ddw_source_chemistry",
        "ddw_source_chemistry_2020_present.csv",
        "d2e74ace-2cf4-4baf-aadd-406280bf1c1c",
        "DDW drinking water source (well) chemistry results, 2020-present (GAMA)",
        prefiltered=True,
    ),
    Dataset(
        "pfas",
        "pfas_statewide.csv",
        "c7cd50a2-2a68-44a1-8d40-4e767f363964",
        "Statewide PFAS results (GAMA); mixes drinking water and cleanup sites",
        date_column="gm_samp_collection_date",
        optional=True,
    ),
]


def _open(url: str, attempts: int = 4):
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "dw-downloader"})
            return urllib.request.urlopen(req, timeout=120)
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == attempts:
                raise
            wait = 2**attempt
            print(f"  retry in {wait}s ({type(exc).__name__})", file=sys.stderr)
            time.sleep(wait)


def resolve_url(resource_id: str) -> str:
    with _open(f"{CKAN}/resource_show?id={resource_id}") as resp:
        payload = json.load(resp)
    if not payload.get("success"):
        raise RuntimeError(f"resource_show failed for {resource_id}")
    return payload["result"]["url"]


def _year(value: str) -> int | None:
    head = value.strip()[:4]
    return int(head) if head.isdigit() else None


def _copy_raw(resp, part: Path) -> None:
    with part.open("wb") as out:
        while chunk := resp.read(CHUNK):
            out.write(chunk)


def _copy_filtered(resp, part: Path, column: str, min_year: int):
    """Stream CSV rows to `part`, dropping rows older than min_year."""
    text = io.TextIOWrapper(resp, encoding="utf-8", errors="replace", newline="")
    reader = csv.reader(text)
    header = next(reader)
    idx = header.index(column)
    rows = kept = 0
    newest = ""
    with part.open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(header)
        for row in reader:
            rows += 1
            if len(row) <= idx:
                continue
            year = _year(row[idx])
            if year is not None and year < min_year:
                continue
            kept += 1
            newest = max(newest, row[idx].strip())
            writer.writerow(row)
    return rows, kept, newest


def _count_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def download(ds: Dataset, min_year: int, force: bool) -> dict:
    target = OUT_DIR / ds.filename
    if target.exists() and not force:
        print(f"  exists, skipping ({target.name}); use --force to re-download")
        return {"file": ds.filename, "skipped": True}

    part = target.with_suffix(".part")
    filter_col = None if ds.prefiltered else ds.date_column
    newest = ""
    started = time.time()

    with _open(resolve_url(ds.resource_id)) as resp:
        if filter_col is None:
            _copy_raw(resp, part)
        else:
            rows, kept, newest = _copy_filtered(resp, part, filter_col, min_year)
    part.replace(target)

    if filter_col is None:
        rows = kept = _count_rows(target)
    size = target.stat().st_size
    print(
        f"  {kept:,} rows kept (of {rows:,}), {size / 1e6:,.1f} MB, "
        f"{time.time() - started:,.0f}s"
    )
    return {
        "file": ds.filename,
        "resource_id": ds.resource_id,
        "description": ds.description,
        "rows_in_file": kept,
        "rows_read": rows,
        "bytes": size,
        "filtered_from_year": min_year if filter_col else None,
        "newest_sample_date": newest or None,
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", nargs="+", metavar="KEY", help="datasets to fetch")
    parser.add_argument("--min-year", type=int, default=2020)
    parser.add_argument("--skip-large", action="store_true", help="skip > 500 MB")
    parser.add_argument("--with-pfas", action="store_true", help="include PFAS")
    parser.add_argument("--force", action="store_true", help="re-download files")
    parser.add_argument("--list", action="store_true", help="list datasets and exit")
    args = parser.parse_args()

    if args.list:
        for ds in DATASETS:
            flag = " (optional, --with-pfas)" if ds.optional else ""
            print(f"{ds.key:22} {ds.description}{flag}")
        return 0

    unknown = set(args.only or []) - {d.key for d in DATASETS}
    if unknown:
        parser.error(f"unknown dataset(s): {', '.join(sorted(unknown))}")

    selected = [
        d
        for d in DATASETS
        if (d.key in args.only if args.only else (args.with_pfas or not d.optional))
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT_DIR / "manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {}
    )

    for ds in selected:
        print(f"[{ds.key}] {ds.description}")
        try:
            if args.skip_large:
                with _open(resolve_url(ds.resource_id)) as probe:
                    if int(probe.headers.get("Content-Length") or 0) > LARGE_BYTES:
                        print("  skipped (large)")
                        continue
            info = download(ds, args.min_year, args.force)
        except Exception as exc:  # keep going so one failure doesn't lose the rest
            print(f"  FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        if not info.get("skipped"):
            manifest[ds.key] = info
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nDone. Files in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
