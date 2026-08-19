"""
Join NASS county-level corn yield data to Census county boundary polygons
on 5-digit FIPS code, clean up, and export Tableau-ready files.

Join key: FIPS = STATE_FIPS_CODE (2-digit) + COUNTY_ANSI (3-digit), matched
against the shapefile's GEOID (STATEFP + COUNTYFP).

Known data-quality issue (documented, not silently dropped): NASS reports
some small/low-count counties per state-year under a catch-all bucket
"OTHER (COMBINED) COUNTIES" (COUNTY_CODE 998) with no COUNTY_ANSI -- these
have no real polygon to join to and are excluded. This is ~7% of raw rows;
see the printed summary and README for the exact count.

Outputs (data/processed/):
  county_boundaries.geojson     -- one polygon per county (FIPS, names, geometry
                                    only), Tableau/GIS ready. A naive export of
                                    the full year-by-year panel with geometry
                                    repeated per row would be ~215MB (each
                                    polygon duplicated 20x, once per year), so
                                    geometry is exported once per county and
                                    meant to be joined to the CSV below on
                                    FIPS -- the standard Tableau "spatial file +
                                    flat file, join on key" pattern.
  corn_yield_by_county.csv      -- full county-year panel (no geometry): FIPS,
                                    state, county, year, yield, cv%.
  corn_yield_latest_year.geojson-- convenience single-file choropleth: latest
                                    year's yield merged directly onto polygons,
                                    for a quick one-file "current yield" map.
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
NASS_CSV = ROOT / "data" / "raw" / "nass_corn_county_yield_2005_2024.csv"
SHAPEFILE = ROOT / "data" / "raw" / "cb_2018_us_county_500k" / "cb_2018_us_county_500k.shp"
PROCESSED_DIR = ROOT / "data" / "processed"


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    nass = pd.read_csv(NASS_CSV, dtype=str)
    n_raw = len(nass)

    # Drop NASS's "OTHER (COMBINED) COUNTIES" catch-all rows -- these
    # aggregate several small counties per state-year and have no ANSI
    # code, so there is no single polygon to join them to.
    no_ansi = nass["COUNTY_ANSI"].isna()
    n_dropped_no_ansi = int(no_ansi.sum())
    nass = nass[~no_ansi].copy()

    nass["FIPS"] = (
        nass["STATE_FIPS_CODE"].str.zfill(2) + nass["COUNTY_ANSI"].str.zfill(3)
    )
    nass["YEAR"] = nass["YEAR"].astype(int)
    nass["VALUE"] = nass["VALUE"].str.replace(",", "", regex=False).astype(float)
    nass = nass.rename(columns={"VALUE": "yield_bu_per_acre", "CV_%": "cv_pct"})

    counties = gpd.read_file(SHAPEFILE)[["GEOID", "STATEFP", "COUNTYFP", "NAME", "geometry"]]
    counties = counties.rename(columns={"GEOID": "FIPS", "NAME": "county_name_census"})

    # Which FIPS in the yield data have no matching polygon, and vice versa?
    yield_fips = set(nass["FIPS"])
    shape_fips = set(counties["FIPS"])
    unmatched_yield_fips = yield_fips - shape_fips
    n_unmatched_rows = int(nass["FIPS"].isin(unmatched_yield_fips).sum())

    merged = counties.merge(nass, on="FIPS", how="inner")

    print("=== Join summary ===")
    print(f"Raw NASS county-year rows:                    {n_raw}")
    print(f"Dropped ('OTHER COMBINED COUNTIES', no ANSI):  {n_dropped_no_ansi}")
    print(f"Rows with FIPS not found in 2018 shapefile:    {n_unmatched_rows} "
          f"({len(unmatched_yield_fips)} distinct FIPS codes)")
    if unmatched_yield_fips:
        sample = sorted(unmatched_yield_fips)[:10]
        print(f"  sample unmatched FIPS: {sample}")
    print(f"Final joined county-year rows:                 {len(merged)}")
    print(f"Distinct counties represented:                 {merged['FIPS'].nunique()}")
    print(f"Years covered:                                 {merged['YEAR'].min()}-{merged['YEAR'].max()}")

    keep_cols = [
        "FIPS", "STATE_ALPHA", "STATE_NAME", "county_name_census", "COUNTY_NAME",
        "YEAR", "yield_bu_per_acre", "cv_pct", "geometry",
    ]
    merged = merged[keep_cols].rename(columns={
        "STATE_ALPHA": "state_abbr",
        "STATE_NAME": "state_name",
        "county_name_census": "county_name",
        "COUNTY_NAME": "county_name_nass",
        "YEAR": "year",
    })
    merged = merged.sort_values(["FIPS", "year"]).reset_index(drop=True)

    boundaries_path = PROCESSED_DIR / "county_boundaries.geojson"
    csv_path = PROCESSED_DIR / "corn_yield_by_county.csv"
    latest_year_path = PROCESSED_DIR / "corn_yield_latest_year.geojson"

    # One polygon per county (drop the year-varying columns + dedupe).
    boundaries = merged.drop_duplicates("FIPS")[
        ["FIPS", "state_abbr", "state_name", "county_name", "geometry"]
    ].reset_index(drop=True)
    boundaries.to_file(boundaries_path, driver="GeoJSON")

    merged.drop(columns="geometry").to_csv(csv_path, index=False)

    latest_year = int(merged["year"].max())
    latest = merged[merged["year"] == latest_year].drop(
        columns=["county_name_nass"]
    ).reset_index(drop=True)
    latest.to_file(latest_year_path, driver="GeoJSON")

    print(f"\nWrote {boundaries_path} ({len(boundaries)} counties)")
    print(f"Wrote {csv_path} ({len(merged)} county-year rows)")
    print(f"Wrote {latest_year_path} (latest year = {latest_year}, {len(latest)} counties)")


if __name__ == "__main__":
    sys.exit(main())
