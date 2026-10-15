"""Trim DDW SDWIS tab files into one small CSV of tap/treated-water results.

Input : datasets/drinking_water/edt/SDWIS*.tab (from the DDW EDT library)
Output: datasets/drinking_water/tap_water_results.csv.gz

Keeps distribution-system (DS), treatment-plant (TP), clear-well (CW) and
consumer-connection (CC) sampling points from 2023 onward. Raw-source facilities
are skipped because source chemistry is already loaded separately.
"""

from __future__ import annotations

import csv
import gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "datasets" / "drinking_water"
KEEP_FACILITIES = {"DS", "TP", "CW", "CC"}
MIN_YEAR = 2023
OUT_COLS = [
    "pws_id",
    "system_name",
    "ps_code",
    "sampling_point",
    "facility_type",
    "sample_type",
    "sample_date",
    "analyte_code",
    "analyte_name",
    "result",
    "units",
    "less_than_rl",
    "reporting_level",
    "dlr",
    "mcl",
    "method",
]


def main() -> None:
    csv.field_size_limit(2**30)
    out_path = ROOT / "tap_water_results.csv.gz"
    n = 0
    with gzip.open(out_path, "wt", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(OUT_COLS)
        for tab in sorted((ROOT / "edt").glob("SDWIS*.tab")):
            with tab.open(encoding="latin-1", newline="") as f:
                r = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
                h = {c.strip(): i for i, c in enumerate(next(r))}
                g = lambda row, c: row[h[c]].strip() if h[c] < len(row) else ""  # noqa: E731
                for row in r:
                    if g(row, "Facility Type") not in KEEP_FACILITIES:
                        continue
                    d = g(row, "Sample Date")  # MM-DD-YYYY
                    if len(d) != 10 or int(d[6:]) < MIN_YEAR:
                        continue
                    w.writerow(
                        [
                            g(row, "Water System Number"),
                            g(row, "Water System Name"),
                            g(row, "PS Code"),
                            g(row, "Sampling Point Name"),
                            g(row, "Facility Type"),
                            g(row, "Sample Type"),
                            f"{d[6:]}-{d[:2]}-{d[3:5]}",
                            g(row, "Analyte Code"),
                            g(row, "Analyte Name"),
                            g(row, "Result"),
                            g(row, "Units of Measure"),
                            g(row, "Less Than Reporting Level"),
                            g(row, "Reporting Level"),
                            g(row, "DLR"),
                            g(row, "MCL"),
                            g(row, "Method"),
                        ]
                    )
                    n += 1
    print(f"Wrote {n} rows to {out_path}")


if __name__ == "__main__":
    main()
