# Real Estate Market Intelligence - Complete Documentation

## Project Overview

**Real Estate Market Intelligence** is an end-to-end analytics platform that helps home buyers and investors search, compare, and evaluate ZIP codes across the United States. It combines real Zillow home value and rental data with neighborhood amenities and school quality metrics into a single searchable platform.

**Tech Stack:** Zillow ZHVI/ZORI (real data) | dbt-fusion | Databricks (Unity Catalog) | Streamlit | Plotly

**Key Metrics:**
- 26,276 ZIP codes analyzed
- 24 months of price/rent history (May 2024 - April 2026)
- Composite livability score (0-100) per ZIP
- Investment signals (STRONG BUY / BUY / HOLD / WATCH)
- Metro-vs-metro comparison across 500+ metros

---

## Table of Contents

1. [Architecture](#1-architecture)
2. [Data Sources](#2-data-sources)
3. [Data Ingestion](#3-data-ingestion)
4. [dbt Project Structure](#4-dbt-project-structure)
5. [Staging Models](#5-staging-models)
6. [Intermediate Models](#6-intermediate-models)
7. [Mart Models](#7-mart-models)
8. [Testing Strategy](#8-testing-strategy)
9. [Visualization Layer](#9-visualization-layer)
10. [How to Run](#10-how-to-run)
11. [Sample Queries](#11-sample-queries)
12. [Best Practices](#12-best-practices)
13. [Future Improvements](#13-future-improvements)

---

## 1. Architecture

```
DATA SOURCES                    INGESTION                   TRANSFORMATION (dbt)                    PRESENTATION
============                    =========                   ====================                    ============

Zillow ZHVI ──→ Download CSV ──→ Python reshape ──→ Upload ──→ raw_home_values    ──→ stg_home_values    ──→ int_price_trends      ──┐
                                                              (realestate_raw)        (realestate_staging)    (realestate_intermediate)  │
Zillow ZORI ──→ Download CSV ──→ Python reshape ──→ Upload ──→ raw_rental_prices  ──→ stg_rental_prices  ──→ int_rental_yield       ──┤
                                                                                                                                       ├──→ market_intelligence ──→ Databricks Dashboard
OpenStreetMap ─→ Simulated   ──→ Upload ──────────→ raw_amenities     ──→ stg_amenities     ──→ int_neighborhood_score ──┤    investment_hotspots     Streamlit Web App
                                                                                                                         │    area_comparison
NCES Schools ──→ Simulated   ──→ Upload ──────────→ raw_schools       ──→ stg_schools       ──→ int_school_score      ──┘
```

### Schema Layout (Databricks Unity Catalog)

| Catalog | Schema | Layer | Materialization | Description |
|---------|--------|-------|-----------------|-------------|
| dbt_hari | realestate_raw | Raw | Delta Tables (uploaded) | Source data from Zillow, OSM, NCES |
| dbt_hari | realestate_staging | Staging | Views | Cleaned, typed, filtered |
| dbt_hari | realestate_intermediate | Intermediate | Views | Business logic, scoring, trends |
| dbt_hari | realestate_marts | Marts | Tables | Final buyer/investor-facing outputs |

---

## 2. Data Sources

### 2.1 Zillow Home Value Index (ZHVI) - REAL DATA
- **Source:** https://www.zillow.com/research/data/
- **Type:** ZHVI All Homes (SFR, Condo/Co-op), Smoothed, Seasonally Adjusted
- **Geography:** ZIP Code level
- **Format:** Wide CSV (one column per month) -> reshaped to long format
- **Coverage:** 26,276 ZIP codes, 316 months (2000-2026), filtered to last 24 months
- **Rows after reshape:** 630,604
- **Fields:** zip_code, city, state, metro, county, date, home_value

### 2.2 Zillow Observed Rent Index (ZORI) - REAL DATA
- **Source:** https://www.zillow.com/research/data/
- **Type:** ZORI (Smoothed), All Homes Plus Multifamily
- **Geography:** ZIP Code level
- **Coverage:** ~6,500 ZIP codes (fewer than ZHVI - rental data not available everywhere)
- **Rows after reshape:** 148,376
- **Fields:** zip_code, city, state, metro, county, date, rental_price

### 2.3 OpenStreetMap Amenities - SIMULATED
- **Methodology:** Generated realistic amenity counts for all 26K Zillow ZIP codes
- **Categories:** Parks, Shopping, Entertainment, Dining
- **Rows:** 591,272
- **Note:** For production, replace with real Overpass API data via Databricks notebook

### 2.4 NCES School Data - SIMULATED
- **Methodology:** Generated realistic school metrics for all ZIP codes
- **Years:** 2017 and 2022 (for 5-year trend analysis)
- **Metrics:** Enrollment, student-teacher ratio, free lunch %, charter/magnet status
- **Rows:** 235,606
- **Note:** For production, replace with real Education Data Portal API data

---

## 3. Data Ingestion

### 3.1 Zillow CSV Download & Reshape

Since Databricks SQL warehouses cannot run Python notebooks, the ingestion process is:

```
Step 1: Manual download from zillow.com/research/data/
        - Select "ZHVI All Homes" -> Geography: "Zip Code" -> Download
        - Select "ZORI All Homes" -> Geography: "ZIP Codes" -> Download

Step 2: Python reshape (local)
        - Wide format (300+ date columns) -> Long format (date, value)
        - Pad ZIP codes to 5 digits
        - Filter to last 24 months
        - Save as CSV

Step 3: Upload to Databricks
        - Catalog -> dbt_hari -> realestate_raw -> Create Table -> Upload CSV
```

### 3.2 File Locations

| File | Rows | Size | Location |
|------|------|------|----------|
| raw_home_values.csv | 630,604 | 62 MB | upload_to_databricks/ |
| raw_rental_prices.csv | 148,376 | 16 MB | upload_to_databricks/ |
| raw_amenities.csv | 591,272 | 37 MB | upload_to_databricks/ |
| raw_schools.csv | 235,606 | 25 MB | upload_to_databricks/ |

### 3.3 Databricks Notebook Alternative

If you upgrade to cluster compute, three notebooks are provided in `notebooks/`:
- `01_ingest_zillow.py` - Downloads Zillow CSVs directly and writes to Delta
- `02_ingest_amenities.py` - Queries OpenStreetMap Overpass API
- `03_ingest_schools.py` - Fetches from NCES Education Data Portal API

---

## 4. dbt Project Structure

```
realestate_intel/
├── dbt_project.yml                          # Project configuration
├── macros/
│   └── generate_schema.sql                  # Exact schema naming (no prefix)
├── models/
│   ├── staging/                             # Layer 1: Clean & type-cast
│   │   ├── _staging.yml                     # Source definitions + 12 tests
│   │   ├── stg_home_values.sql              # Zillow ZHVI cleanup
│   │   ├── stg_rental_prices.sql            # Zillow ZORI cleanup
│   │   ├── stg_amenities.sql                # OSM amenity cleanup
│   │   └── stg_schools.sql                  # NCES school cleanup
│   ├── intermediate/                        # Layer 2: Business logic
│   │   ├── _intermediate.yml                # 8 tests
│   │   ├── int_price_trends.sql             # 30d/6m/1yr price analysis
│   │   ├── int_rental_yield.sql             # Gross yield + trends
│   │   ├── int_neighborhood_score.sql       # Amenity scoring (0-100)
│   │   └── int_school_score.sql             # School scoring (0-100)
│   └── marts/                               # Layer 3: Consumer-facing
│       ├── _marts.yml                       # 6 tests
│       ├── market_intelligence.sql          # Main buyer search table
│       ├── investment_hotspots.sql          # Investment signals
│       └── area_comparison.sql              # Metro-level aggregation
├── notebooks/                               # Databricks ingestion (cluster-only)
│   ├── 01_ingest_zillow.py
│   ├── 02_ingest_amenities.py
│   └── 03_ingest_schools.py
├── streamlit_app/                           # Web application
│   ├── app.py                               # Streamlit interactive app
│   └── requirements.txt                     # Python dependencies
└── upload_to_databricks/                    # Reshaped CSVs for upload
```

### Configuration

**dbt_project.yml:**
- Staging models: `+materialized: view` in schema `realestate_staging`
- Intermediate models: `+materialized: view` in schema `realestate_intermediate`
- Mart models: `+materialized: table` in schema `realestate_marts`

**generate_schema.sql macro:**
- Overrides dbt default to use exact schema names without target prefix
- Same pattern used across all three projects (ecommerce, lending, realestate)

**Profile (in ~/.dbt/profiles.yml):**
```yaml
realestate_intel:
  outputs:
    dev:
      type: databricks
      catalog: dbt_hari
      host: dbc-9035745e-5721.cloud.databricks.com
      http_path: /sql/1.0/warehouses/7ff837a343b54036
      schema: realestate
      threads: 1
```

---

## 5. Staging Models

### 5.1 stg_home_values
**Source:** `realestate_raw.raw_home_values`
**Purpose:** Clean and type-cast Zillow home value time series

| Column | Type | Description |
|--------|------|-------------|
| zip_code | string | 5-digit ZIP code |
| city | string | City name |
| state | string | 2-letter state abbreviation |
| state_name | string | Full state name |
| metro | string | Metropolitan statistical area |
| county | string | County name |
| date | date | Month of observation |
| home_value | double | Zillow Home Value Index ($) |
| region_id | int | Zillow region identifier |
| size_rank | int | Population size ranking |

**Filters applied:** `home_value IS NOT NULL AND home_value > 0`

### 5.2 stg_rental_prices
**Source:** `realestate_raw.raw_rental_prices`
**Purpose:** Clean rental price time series

Same structure as stg_home_values but with `rental_price` instead of `home_value`.

**Filters applied:** `rental_price IS NOT NULL AND rental_price > 0`

### 5.3 stg_amenities
**Source:** `realestate_raw.raw_amenities`
**Purpose:** Clean amenity records with category classification

| Column | Type | Description |
|--------|------|-------------|
| zip_code | string | 5-digit ZIP code |
| amenity_name | string | Name of the amenity |
| amenity_type | string | Specific type (park, cinema, restaurant, etc.) |
| amenity_category | string | Category: parks, shopping, entertainment, dining |
| latitude | double | Geographic latitude |
| longitude | double | Geographic longitude |
| city | string | City name |
| state_name | string | Full state name |

### 5.4 stg_schools
**Source:** `realestate_raw.raw_schools`
**Purpose:** Clean school records with derived metrics

| Column | Type | Description |
|--------|------|-------------|
| nces_school_id | string | National school identifier |
| school_name | string | School name |
| zip_code | string | 5-digit ZIP code |
| school_level | int | 1=Primary, 2=Middle, 3=High |
| school_level_name | string | Human-readable level label |
| enrollment | int | Student enrollment count |
| teachers_fte | double | Full-time equivalent teachers |
| student_teacher_ratio | double | Students per teacher |
| free_lunch_pct | double | Free/reduced lunch percentage |
| year | int | Data year (2017 or 2022) |

**Best Practice:** Staging models are views (not tables) to avoid data duplication. They only clean and type-cast; no business logic.

---

## 6. Intermediate Models

### 6.1 int_price_trends
**Purpose:** Calculate 30-day, 6-month, and 1-year price appreciation per ZIP

**Key Logic:**
```sql
-- Join current values to historical values at each lookback window
-- using add_months() for precise date arithmetic
left join home_values hv_1yr
    on cv.zip_code = hv_1yr.zip_code
    and hv_1yr.date = add_months(cv.current_date, -12)
```

**Output Fields:**

| Field | Description |
|-------|-------------|
| current_value | Latest month home value |
| pct_change_30d | 1-month price change (%) |
| pct_change_6m | 6-month price change (%) |
| pct_change_1yr | 1-year price change (%) |
| dollar_change_1yr | Absolute dollar change |
| annual_appreciation_rate | Year-over-year growth rate |
| price_trend | strong_appreciation / moderate_appreciation / stable / moderate_decline / strong_decline |
| price_momentum | accelerating / decelerating |

**Trend Classification:**
- > 5% annual = strong_appreciation
- 1-5% = moderate_appreciation
- -1% to 1% = stable
- -5% to -1% = moderate_decline
- < -5% = strong_decline

### 6.2 int_rental_yield
**Purpose:** Calculate gross rental yield and yield trends

**Key Formula:**
```
gross_rental_yield = (monthly_rent * 12) / home_value * 100
```

**Output Fields:**

| Field | Description |
|-------|-------------|
| current_rent | Latest monthly rent |
| current_value | Latest home value |
| current_yield | Gross annual yield (%) |
| yield_30d_ago / 6m / 1yr | Historical yields |
| yield_change_1yr_bps | Yield change in basis points |
| rent_growth_1yr_pct | Annual rent growth (%) |
| yield_tier | premium (8%+) / strong (6-8%) / average (4-6%) / below_average (2-4%) / low (<2%) |
| yield_trend | improving / compressing / stable |

### 6.3 int_neighborhood_score
**Purpose:** Score neighborhoods on parks, shopping, entertainment, dining

**Scoring Method:** Percentile ranking within the full dataset (0-100 scale)
```sql
round(percent_rank() over (order by parks_count) * 100, 1) as parks_score
```

**Composite Score Weights:**
- Parks: 30%
- Shopping: 20%
- Entertainment: 25%
- Dining: 25%

**Tier Classification:** excellent (80+) / good (60-80) / average (40-60) / below_average (20-40) / poor (<20)

### 6.4 int_school_score
**Purpose:** Score school quality with 5-year trend analysis

**Data:** Compares 2022 metrics to 2017 for trend detection

**Component Scores:**
- Student-teacher ratio score (40%) - lower ratio = higher score
- School choice score (30%) - more schools = higher score
- Level diversity score (30%) - having primary + middle + high = 100

**Trend Detection:**
- `improving`: student-teacher ratio decreased AND enrollment grew
- `declining`: student-teacher ratio increased AND enrollment dropped
- `stable`: everything else

---

## 7. Mart Models

### 7.1 market_intelligence (Primary Table)
**Purpose:** The main buyer search table. One row per ZIP code combining all metrics.

**Joins:**
```
int_price_trends (required)
  LEFT JOIN int_rental_yield (not all ZIPs have rental data)
  LEFT JOIN int_neighborhood_score (amenity coverage varies)
  LEFT JOIN int_school_score (school coverage varies)
```

**Composite Livability Score (0-100):**
```
Price trend component (25%):  map appreciation rate to 0-100
Rental yield component (20%): map yield to 0-100
Neighborhood score (30%):     directly from int_neighborhood_score
School score (25%):           directly from int_school_score
```

**Livability Tiers:**
- A - Premium: score >= 80
- B - Good: 60-80
- C - Average: 40-60
- D - Below Average: 20-40
- F - Poor: < 20

**Metro Ranking:** Each ZIP is ranked within its metro area by livability score.

### 7.2 investment_hotspots
**Purpose:** Investment-focused view with buy/sell signals

**Investment Score (0-100):**
- Rental yield: 35%
- Price appreciation: 35%
- Neighborhood: 15%
- Schools: 15%

**Cash-on-Cash Estimate:**
```sql
(monthly_rent * 12) / (home_value * 0.25) * 100
-- Assumes 25% down payment, simplified (no expenses)
```

**Investment Signals:**
| Signal | Criteria |
|--------|----------|
| STRONG BUY | Yield >= 6% AND appreciation > 2% AND neighborhood >= 50 |
| BUY | Yield >= 4% AND appreciation > 0% AND neighborhood >= 30 |
| HOLD | Yield >= 3% AND appreciation > -2% |
| WATCH | Everything else |

### 7.3 area_comparison
**Purpose:** Metro-level aggregation for city-vs-city comparison

**Aggregations per metro:**
- ZIP count, median/avg/min/max home value
- Average rent, yield, appreciation rate
- Average neighborhood and school scores
- Average livability score
- % of ZIPs appreciating vs declining

---

## 8. Testing Strategy

### Test Summary: 35 tests, all passing

| Layer | Tests | Types |
|-------|-------|-------|
| Staging | 12 | not_null, accepted_values |
| Intermediate | 12 | unique, not_null, accepted_values |
| Marts | 11 | unique, not_null, accepted_values |

### Test Details by Model

**Staging tests:**
- `stg_home_values`: not_null on zip_code, date, home_value
- `stg_rental_prices`: not_null on zip_code, date, rental_price
- `stg_amenities`: not_null on zip_code, amenity_category; accepted_values for categories
- `stg_schools`: not_null on nces_school_id, zip_code, year; accepted_values for year

**Intermediate tests:**
- All 4 models: unique + not_null on zip_code
- Accepted_values on tier/trend columns (price_trend, yield_tier, neighborhood_tier, school_tier)

**Mart tests:**
- `market_intelligence`: unique + not_null on zip_code, not_null on livability_score, accepted_values on livability_tier
- `investment_hotspots`: unique + not_null on zip_code, accepted_values on investment_signal
- `area_comparison`: unique + not_null on metro, not_null on avg_livability_score

### dbt-fusion YAML Pattern
All `accepted_values` and `relationships` tests use the `arguments:` nesting pattern required by dbt-fusion:
```yaml
- accepted_values:
    arguments:
      values: ['A', 'B', 'C']
```

---

## 9. Visualization Layer

### 9.1 Databricks SQL Dashboard
- **Location:** Databricks workspace -> Dashboards
- **Built with:** Genie Code (AI-generated)
- **Widgets:**
  - Filter by State (multi-select)
  - Total ZIP Codes counter (26.28K)
  - Average Rental Yield by Metro (bar chart)
  - Average Livability Score by Metro (bar chart)
  - ZIP Codes by Livability Tier (pie chart)
  - Top Investment Hotspots (table)
- **Refresh:** Live from Databricks SQL Warehouse

### 9.2 Streamlit Web App
- **Location:** `streamlit_app/app.py`
- **URL:** http://localhost:8502
- **Connection:** Direct to Databricks SQL via `databricks-sql-connector`

**Features:**

| Tab | Description |
|-----|-------------|
| Buyer Search | Filter by state, metro, price, scores -> top ZIPs table + charts |
| Investment Hotspots | STRONG BUY/BUY/HOLD/WATCH signals, yield vs appreciation scatter |
| Metro Comparison | Top metros bar chart, metro detail table, value vs yield scatter |
| Trends | Price trend distribution, yield tier pie chart, neighborhood vs school scatter |

**Sidebar Filters:**
- State (multi-select)
- Metro Area (multi-select, filtered by state)
- Home Value range (slider, $0 - $2M)
- Minimum Livability Score (slider, 0-100)
- Minimum Neighborhood Score (slider, 0-100)
- Minimum School Score (slider, 0-100)
- Minimum Gross Yield % (slider, 0-15%)

**Dependencies:** streamlit, pandas, plotly, databricks-sql-connector

---

## 10. How to Run

### Prerequisites
- Python 3.11+
- dbt-fusion 2.0.0+ (`C:\Users\haris\.local\bin\dbt.exe`)
- Databricks workspace with SQL warehouse
- Profile `realestate_intel` in `~/.dbt/profiles.yml`

### Step 1: Data Ingestion (one-time)
```bash
# Data already uploaded to dbt_hari.realestate_raw
# To refresh: re-download Zillow CSVs, run Python reshape, re-upload
```

### Step 2: dbt Build
```bash
cd C:\Users\haris\OneDrive\Desktop\c\.vscode\DBT-Hari\realestate_intel
C:\Users\haris\.local\bin\dbt.exe debug    # verify connection
C:\Users\haris\.local\bin\dbt.exe build    # run all models + tests
```

### Step 3: Launch Streamlit
```bash
cd streamlit_app
pip install -r requirements.txt
python -m streamlit run app.py
# Opens at http://localhost:8502
```

### Step 4: Databricks Dashboard
- Already published in Databricks workspace
- Access via Dashboards -> "Real Estate Market Intelligence"

---

## 11. Sample Queries

### Query 1: Top 10 Most Livable ZIPs
```sql
SELECT zip_code, city, state, metro,
       home_value, monthly_rent, gross_rental_yield,
       neighborhood_score, school_score,
       livability_score, livability_tier, metro_rank
FROM dbt_hari.realestate_marts.market_intelligence
ORDER BY livability_score DESC
LIMIT 10;
```

### Query 2: STRONG BUY Investment Opportunities
```sql
SELECT zip_code, city, state, metro,
       home_value, monthly_rent, gross_rental_yield,
       annual_appreciation_rate, investment_score,
       cash_on_cash_estimate, investment_signal
FROM dbt_hari.realestate_marts.investment_hotspots
WHERE investment_signal = 'STRONG BUY'
ORDER BY investment_score DESC
LIMIT 10;
```

### Query 3: Compare Two Metros
```sql
SELECT metro, zip_count, median_home_value, avg_monthly_rent,
       avg_rental_yield, avg_appreciation_rate,
       avg_neighborhood_score, avg_school_score,
       avg_livability_score, pct_appreciating
FROM dbt_hari.realestate_marts.area_comparison
WHERE metro LIKE '%Dallas%' OR metro LIKE '%Austin%'
ORDER BY avg_livability_score DESC;
```

### Query 4: Affordable ZIPs with Good Schools
```sql
SELECT zip_code, city, state, metro,
       home_value, school_score, school_tier,
       livability_score
FROM dbt_hari.realestate_marts.market_intelligence
WHERE home_value < 300000
  AND school_score >= 70
ORDER BY livability_score DESC
LIMIT 20;
```

### Query 5: High Yield with Appreciating Prices
```sql
SELECT zip_code, city, state,
       home_value, gross_rental_yield, price_change_1yr_pct,
       investment_signal
FROM dbt_hari.realestate_marts.investment_hotspots
WHERE gross_rental_yield >= 8
  AND annual_appreciation_rate > 3
ORDER BY investment_score DESC;
```

---

## 12. Best Practices

### 12.1 ELT Paradigm
- **Extract:** Download Zillow CSVs, reshape with Python
- **Load:** Upload to Databricks Delta tables (realestate_raw)
- **Transform:** dbt handles all transformations in SQL

### 12.2 Materialization Strategy
| Layer | Materialization | Rationale |
|-------|-----------------|-----------|
| Staging | View | Avoid data duplication; source data is already in Delta |
| Intermediate | View | Complex joins but read infrequently; views save storage |
| Marts | Table | Queried frequently by dashboards/apps; tables = fast reads |

### 12.3 Schema Naming
The `generate_schema.sql` macro ensures exact schema names:
- `realestate_raw` (not `realestate_realestate_raw`)
- `realestate_staging` (not `realestate_realestate_staging`)

### 12.4 Scoring Methodology
- All scores normalized to 0-100 scale using `percent_rank()`
- Composite scores use weighted averages with documented weights
- Tier classifications use consistent breakpoints (80/60/40/20)

### 12.5 Handling Missing Data
- LEFT JOINs in marts (not all ZIPs have rental/amenity/school data)
- COALESCE with sensible defaults (0 for counts, 50 for scores)
- Null-safe division with `NULLIF(denominator, 0)`

### 12.6 dbt-fusion Compatibility
- All `accepted_values` tests use `arguments:` nesting
- All `relationships` tests use `arguments:` nesting
- This differs from dbt-core syntax and is required by dbt-fusion

---

## 13. Future Improvements

### 13.1 Data Quality
| Improvement | Impact | Effort |
|-------------|--------|--------|
| Replace simulated amenities with real OpenStreetMap data | High | Medium (needs cluster compute) |
| Replace simulated schools with real NCES API data | High | Medium (needs cluster compute) |
| Add full Zillow history (26 years, not just 2) | Medium | Low (larger CSV upload) |
| Add ZHVI by bedroom count (1BR, 2BR, 3BR, etc.) | Medium | Low |

### 13.2 Additional Data Sources
| Source | Data | Cost | Integration |
|--------|------|------|-------------|
| FRED API | Mortgage rates, economic indicators | Free | API + dbt source |
| HUD Fair Market Rents | Official rent benchmarks | Free | API + dbt source |
| Census ACS | Demographics, income, population | Free | CSV download |
| Walk Score API | Walkability, transit, bike scores | Paid ($) | API |
| GreatSchools API | Detailed school ratings | Paid ($53/mo) | API |

### 13.3 Model Enhancements
- **Affordability index:** Income-to-price ratio using Census data
- **Mortgage calculator:** Monthly payment estimates at current rates
- **Forecasting:** ZHVF (Zillow Home Value Forecast) integration
- **Seasonality detection:** Identify best months to buy per market
- **Risk scoring:** Combine multiple signals into a market risk score

### 13.4 Platform Improvements
- **Streamlit Cloud deployment:** Host publicly (free tier available)
- **User authentication:** Save searches, set alerts
- **Email alerts:** Notify when a ZIP meets criteria
- **Map visualization:** Interactive choropleth map with Mapbox
- **PDF report generation:** Downloadable area comparison reports
- **Mobile responsive:** Optimize Streamlit layout for mobile

### 13.5 Performance Optimization
- **Incremental models:** Only process new monthly data (not full rebuild)
- **Clustering:** Cluster mart tables by state/metro for faster queries
- **Caching:** Redis cache for Streamlit to reduce Databricks queries
- **Partitioning:** Partition raw tables by date for efficient lookbacks

---

## Appendix A: Model Lineage (DAG)

```
Sources (realestate_raw)
    │
    ├── raw_home_values ──→ stg_home_values ──→ int_price_trends ──────┐
    │                                                                    │
    ├── raw_rental_prices → stg_rental_prices → int_rental_yield ──────┤
    │                                                                    ├──→ market_intelligence ──→ investment_hotspots
    ├── raw_amenities ────→ stg_amenities ───→ int_neighborhood_score ──┤                        ──→ area_comparison
    │                                                                    │
    └── raw_schools ──────→ stg_schools ─────→ int_school_score ───────┘
```

## Appendix B: Scoring Weights Summary

| Score | Components | Weights |
|-------|-----------|---------|
| Neighborhood Score | Parks (30%), Shopping (20%), Entertainment (25%), Dining (25%) | Percentile-based |
| School Score | Student-teacher ratio (40%), School choice (30%), Level diversity (30%) | Percentile-based |
| Livability Score | Price trend (25%), Rental yield (20%), Neighborhood (30%), Schools (25%) | Normalized 0-100 |
| Investment Score | Rental yield (35%), Appreciation (35%), Neighborhood (15%), Schools (15%) | Normalized 0-100 |

## Appendix C: All Project Files

| File | Lines | Purpose |
|------|-------|---------|
| dbt_project.yml | 25 | Project configuration |
| macros/generate_schema.sql | 7 | Schema naming override |
| models/staging/_staging.yml | 55 | Sources + 12 tests |
| models/staging/stg_home_values.sql | 22 | ZHVI cleanup |
| models/staging/stg_rental_prices.sql | 22 | ZORI cleanup |
| models/staging/stg_amenities.sql | 19 | Amenity cleanup |
| models/staging/stg_schools.sql | 38 | School cleanup + labels |
| models/intermediate/_intermediate.yml | 50 | 8 tests |
| models/intermediate/int_price_trends.sql | 90 | Price trend analysis |
| models/intermediate/int_rental_yield.sql | 95 | Rental yield analysis |
| models/intermediate/int_neighborhood_score.sql | 65 | Amenity scoring |
| models/intermediate/int_school_score.sql | 105 | School scoring |
| models/marts/_marts.yml | 45 | 6 tests |
| models/marts/market_intelligence.sql | 130 | Main buyer search table |
| models/marts/investment_hotspots.sql | 70 | Investment signals |
| models/marts/area_comparison.sql | 65 | Metro comparison |
| streamlit_app/app.py | 330 | Interactive web application |
| streamlit_app/requirements.txt | 4 | Python dependencies |
| notebooks/01_ingest_zillow.py | 90 | Zillow ingestion (cluster) |
| notebooks/02_ingest_amenities.py | 120 | OSM ingestion (cluster) |
| notebooks/03_ingest_schools.py | 110 | NCES ingestion (cluster) |

**Total: 11 models | 35 tests | 26 tests passing | 3 notebooks | 1 web app**
