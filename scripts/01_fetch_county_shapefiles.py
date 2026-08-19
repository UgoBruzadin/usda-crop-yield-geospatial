"""
Fetch US county boundary polygons from the Census Bureau's TIGER/Line
cartographic boundary files (public, no key required).

Vintage: 2018, 500k resolution (generalized for thematic mapping, small
file size). Chosen over a newer vintage because it predates Connecticut's
2022 switch from counties to "planning regions" as county-equivalents --
NASS Quick Stats still reports Connecticut by the traditional county FIPS
codes, so a pre-2022 boundary vintage joins cleanly without extra remapping.

Source: https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_county_500k.zip
"""
import io
import sys
import zipfile
from pathlib import Path

import requests

SHAPEFILE_URL = "https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_county_500k.zip"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "cb_2018_us_county_500k"


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {SHAPEFILE_URL} ...")
    resp = requests.get(SHAPEFILE_URL, timeout=60)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        zf.extractall(RAW_DIR)

    shp_files = list(RAW_DIR.glob("*.shp"))
    print(f"Extracted {len(shp_files)} shapefile(s) -> {RAW_DIR}")
    for f in shp_files:
        print(f"  {f.name}")


if __name__ == "__main__":
    sys.exit(main())
