# USDA Corn Yield by County (2005-2024)

A small, real, portfolio-scale GeoPandas project: US county-level corn
(grain) yield from USDA NASS, joined to Census county boundaries, cleaned
into a Tableau-Public-ready dataset, with a Jupyter notebook doing the EDA
and sanity-check maps.

This is intentionally scoped small -- one crop, one metric (yield), a
20-year window, a straightforward attribute join on FIPS code. No API key
was needed anywhere in this pipeline.

## Data sources (exact, dated)

1. **USDA NASS Quick Stats -- bulk crops flat file** (keyless, no API key)
   - Page: https://www.nass.usda.gov/datasets/
   - File used: `qs.crops_20260819.txt.gz` (~1.05 GB gzipped, all
     commodities/years/geographic levels for the CROPS sector). The
     filename is date-stamped and changes whenever NASS refreshes it, so
     `scripts/00_fetch_nass_data.py` scrapes the current filename from the
     datasets page at run time rather than hardcoding this date.
   - We never save this 1GB+ file to disk: it's streamed, gunzipped, and
     filtered in one pass to just county-level corn grain yield.
   - Filtered to: `COMMODITY_DESC=CORN`, `STATISTICCAT_DESC=YIELD`,
     `UNIT_DESC=BU / ACRE` (grain, not silage), `AGG_LEVEL_DESC=COUNTY`,
     `DOMAIN_DESC=TOTAL`, `PRODN_PRACTICE_DESC=ALL PRODUCTION PRACTICES`
     (excludes irrigated-only/non-irrigated splits), years 2005-2024.

2. **US Census Bureau cartographic boundary file, 2018 vintage, 500k
   resolution**
   - `https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_county_500k.zip`
   - Chosen (over a newer vintage) because it predates Connecticut's 2022
     switch from counties to "planning region" county-equivalents; NASS
     still reports Connecticut on the traditional county FIPS codes, so a
     pre-2022 boundary vintage joins without extra remapping.

Join key: 5-digit FIPS = `STATE_FIPS_CODE` (2-digit) + `COUNTY_ANSI`
(3-digit), matched to the shapefile's `GEOID`.

## Reproduce

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python scripts/00_fetch_nass_data.py          # ~3 min, streams+filters the NASS bulk file
python scripts/01_fetch_county_shapefiles.py  # downloads Census county polygons
python scripts/02_join_and_clean.py           # joins on FIPS, writes data/processed/

jupyter nbconvert --to notebook --execute --inplace notebooks/analysis.ipynb
```

`data/raw/` is gitignored (the NASS bulk source is huge and gets re-derived
by rerunning script 00; the Census shapefile is small but also re-fetched
on demand). `data/processed/` is committed since it's the actual
deliverable.

## Data quality notes (handled explicitly, not silently dropped)

- **33,951** raw county-year corn-yield rows came out of the NASS filter.
- **2,510 rows (~7%)** were excluded: NASS bundles some small/low-count
  counties per state-year into an "OTHER (COMBINED) COUNTIES" catch-all
  (internal code 998) with no county FIPS, so there's no single polygon to
  join them to.
- The remaining **31,441 rows joined to Census county polygons with 0
  unmatched FIPS codes** -- every corn-reporting county in the filtered
  NASS data exists in the 2018 Census boundary file.
- **2,248 distinct counties** are represented across the 20-year window,
  spanning **41 states**.
- Reporting coverage is **not** flat over time: ~1,900-2,100 counties
  report per year in 2005-2010, dropping to ~1,250-1,700/year in more
  recent years, with 2024 (the last year in the window) having the fewest
  reporting counties (1,267). This reflects NASS disclosure thresholds and
  later-year data still being preliminary -- it is a real feature of the
  survey, not a join artifact (confirmed by the 0-unmatched-FIPS result
  above).
- **Watch the FIPS dtype.** Several state FIPS codes are single digits
  with a leading zero (e.g. Alabama = `01`, Colorado = `08`). The CSV
  stores `FIPS` correctly as zero-padded text, but a naive numeric read
  (in pandas, Tableau, or elsewhere) will silently strip the leading zero
  and break the join to the GeoJSON. Always read/treat `FIPS` as text.

## What's in `data/processed/` (the Tableau-ready deliverable)

A single 20-year panel with geometry repeated on every row would be
~215 MB (each county polygon duplicated 20x). Instead:

- **`county_boundaries.geojson`** (16 MB, 2,248 features) -- one polygon
  per county: `FIPS`, `state_abbr`, `state_name`, `county_name`,
  `geometry`. This is the spatial file.
- **`corn_yield_by_county.csv`** (1.4 MB, 31,441 rows) -- the full
  county-year panel, no geometry: `FIPS`, `state_abbr`, `state_name`,
  `county_name`, `county_name_nass`, `year`, `yield_bu_per_acre`, `cv_pct`.
  Join this to the boundaries file on `FIPS` in Tableau.
- **`corn_yield_latest_year.geojson`** (8.2 MB, 1,267 features) -- a
  convenience single-file export: 2024 yield already merged onto
  polygons, for a quick one-file choropleth with no join required.

## Notebook (`notebooks/analysis.ipynb`)

Real, executed EDA + sanity-check maps. Headline findings:

- **National trend**: county-average corn yield rose from ~123 bu/acre
  (2005) to ~155 bu/acre (2024) -- a linear trend of about **+2.25
  bu/acre per year** (~+43 bu/acre, +25%, over the full window),
  consistent with the well-documented long-run genetic/agronomic
  improvement trend in US corn.
- **2012 drought anomaly, clearly visible**: national county-average
  yield fell **-9.8%** from 2011 to 2012 (the severe 2012 Midwest
  drought), then rebounded **+30.6%** in 2013. This is a strong signal
  that the pipeline is faithfully reproducing a real historical event.
- **Most productive counties** (>=10 years reported, ranked by mean
  yield): Franklin & Grant, WA; Phelps & Hamilton, NE; Yakima, WA;
  Owyhee & Payette, ID; Hartley & Castro, TX; Meade, KS -- all
  **irrigated** corn country, consistently above 200 bu/acre.
- **Least productive counties**: Lincoln, Elbert & Kiowa, CO; Noble &
  Grant, OK; Mellette & Haakon, SD; Slope, Golden Valley & Billings, ND
  -- marginal **dryland** corn at the edge of its climatic range,
  averaging 50-65 bu/acre.
- Largest single-county year-over-year drops cluster heavily in 2012.

## Building the Tableau Public dashboard

1. Install **Tableau Public Desktop** (free) and open it.
2. **Connect > Spatial file** and point it at
   `data/processed/county_boundaries.geojson`.
3. **Connect > Text file** and add `data/processed/corn_yield_by_county.csv`.
4. In the Data Source tab, create a **relationship/join** between the two
   on `FIPS` (make sure Tableau reads `FIPS` as a **String**, not a
   Number -- see the leading-zero note above, or Colorado/Alabama/etc.
   counties will silently fail to join).
5. Suggested sheets, based on what the notebook actually found:
   - **County choropleth of latest-year yield** -- drag the joined
     geometry to the view, color by `yield_bu_per_acre`, filter
     `year = 2024` (or use `corn_yield_latest_year.geojson` directly for
     a simpler one-file version of this exact sheet).
   - **State-average yield time series (2005-2024)** -- line chart, one
     line per state, to show the shared upward trend and how sharply
     every corn state dips together in 2012.
   - **Year-over-year % change choropleth, 2011 -> 2012** -- the drought
     map from the notebook; a calculated field
     `(SUM([yield]) - LOOKUP(SUM([yield]), -1)) / LOOKUP(SUM([yield]), -1)`
     over `year`, colored red-to-green, makes a strong before/after story.
   - **Irrigated-West vs. dryland-Plains comparison** -- a highlight
     table or bar chart of the top-10/bottom-10 counties from the
     notebook's Section 5, to make the irrigation story concrete.
   - **Dashboard**: combine the latest-year map + state time series +
     a year filter/parameter so a viewer can scrub through 2005-2024 and
     watch 2012 stand out on the map.

## Stack

Python 3.11, geopandas 1.1.4, pandas 3.0.5, shapely 2.1.2, pyogrio 0.13.0
(GeoPandas' I/O backend -- avoids separate GDAL/fiona build hassles),
matplotlib 3.11.1, requests, Jupyter. See `requirements.txt` for the full
pinned list.

## Repo layout

```
scripts/00_fetch_nass_data.py          # stream+filter NASS bulk file -> data/raw/*.csv
scripts/01_fetch_county_shapefiles.py  # download Census boundaries -> data/raw/
scripts/02_join_and_clean.py           # FIPS join + clean -> data/processed/
notebooks/analysis.ipynb               # EDA + sanity-check choropleths
data/processed/                        # the Tableau-ready deliverable (committed)
data/raw/                              # gitignored, re-derived by scripts 00/01
figures/                               # PNGs saved by the notebook
```
