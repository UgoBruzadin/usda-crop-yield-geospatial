"""
Fetch county-level corn yield data from USDA NASS Quick Stats.

Keyless path (no API key needed): USDA NASS publishes a bulk flat-file dump
of the entire CROPS sector (all commodities, all years, all geographic
levels) at https://www.nass.usda.gov/datasets/. That file is ~1GB gzipped
and covers far more than we need, so instead of saving it whole we stream
it: download -> gunzip -> filter to CORN/YIELD/COUNTY rows -> write out.
This keeps disk usage and runtime small (~3 min end to end) while still
using a real, public, keyless USDA source.

Filters applied (see USDA Quick Stats glossary for field definitions):
  COMMODITY_DESC   == "CORN"
  STATISTICCAT_DESC== "YIELD"
  UNIT_DESC        == "BU / ACRE"   (grain corn yield, not silage)
  AGG_LEVEL_DESC   == "COUNTY"
  DOMAIN_DESC      == "TOTAL"       (excludes program/practice breakouts)
  PRODN_PRACTICE_DESC == "ALL PRODUCTION PRACTICES"  (excludes irrigated-
                                                        only / non-irrigated
                                                        splits, keeps the
                                                        county total)
  YEAR in [START_YEAR, END_YEAR]

Output: data/raw/nass_corn_county_yield_<start>_<end>.csv (gitignored)
"""
import csv
import gzip
import re
import sys
from pathlib import Path

import requests

# The bulk file name is date-stamped and changes whenever NASS refreshes it
# (observed as "qs.crops_20260819.txt.gz" on 2026-08-19), so we look up the
# current name from the datasets page rather than hardcoding a date that
# will eventually 404. Falls back to the known-good name from this run.
NASS_DATASETS_PAGE = "https://www.nass.usda.gov/datasets/"
FALLBACK_BULK_URL = "https://www.nass.usda.gov/datasets/qs.crops_20260819.txt.gz"
START_YEAR = 2005
END_YEAR = 2024


def resolve_bulk_url():
    try:
        resp = requests.get(NASS_DATASETS_PAGE, timeout=30)
        resp.raise_for_status()
        match = re.search(r"qs\.crops_\d+\.txt\.gz", resp.text)
        if match:
            return NASS_DATASETS_PAGE + match.group(0)
    except requests.RequestException as e:
        print(f"Could not resolve current bulk filename ({e}); using fallback.")
    return FALLBACK_BULK_URL

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT_PATH = RAW_DIR / f"nass_corn_county_yield_{START_YEAR}_{END_YEAR}.csv"

KEEP_COLS = [
    "STATE_ALPHA", "STATE_NAME", "STATE_FIPS_CODE", "COUNTY_ANSI",
    "COUNTY_NAME", "YEAR", "VALUE", "CV_%",
]


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    bulk_url = resolve_bulk_url()
    print(f"Streaming {bulk_url} ...")

    n_written = 0
    with requests.get(bulk_url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        # gzip.GzipFile can wrap any file-like object with a .read(), so we
        # decompress on the fly as bytes stream in -- no multi-GB temp file.
        gz_stream = gzip.GzipFile(fileobj=resp.raw)
        text_stream = (line.decode("utf-8", errors="replace") for line in gz_stream)
        reader = csv.DictReader(text_stream, delimiter="\t")

        with open(OUT_PATH, "w", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=KEEP_COLS)
            writer.writeheader()
            for row in reader:
                if (
                    row["COMMODITY_DESC"] == "CORN"
                    and row["STATISTICCAT_DESC"] == "YIELD"
                    and row["UNIT_DESC"] == "BU / ACRE"
                    and row["AGG_LEVEL_DESC"] == "COUNTY"
                    and row["DOMAIN_DESC"] == "TOTAL"
                    and row["PRODN_PRACTICE_DESC"] == "ALL PRODUCTION PRACTICES"
                    and row["YEAR"].isdigit()
                    and START_YEAR <= int(row["YEAR"]) <= END_YEAR
                ):
                    writer.writerow({k: row[k] for k in KEEP_COLS})
                    n_written += 1

    print(f"Wrote {n_written} county-year corn yield rows -> {OUT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
