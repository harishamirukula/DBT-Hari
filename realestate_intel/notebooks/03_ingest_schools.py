# Databricks notebook source
# MAGIC %md
# MAGIC # Real Estate Intelligence — Data Ingestion
# MAGIC ## Part 3: School Ratings (NCES / Urban Institute Education Data Portal)
# MAGIC
# MAGIC Fetches public school data from the Urban Institute's Education Data Portal API.
# MAGIC Free, no API key required.
# MAGIC
# MAGIC Source: https://educationdata.urban.org/

# COMMAND ----------

import requests
import pandas as pd
import time

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1. Get unique states from our Zillow data

# COMMAND ----------

states = spark.sql("""
    SELECT DISTINCT state
    FROM dbt_hari.realestate_raw.raw_home_values
    WHERE state IS NOT NULL
    ORDER BY state
""").toPandas()['state'].tolist()

print(f"States to query: {len(states)}")
print(states)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2. Fetch school directory data from Education Data Portal
# MAGIC
# MAGIC API endpoint: `https://educationdata.urban.org/api/v1/schools/ccd/directory/{year}/`
# MAGIC
# MAGIC Includes: school name, ZIP, enrollment, school type, charter status, Title I, etc.

# COMMAND ----------

def fetch_schools_for_state(state_abbr, year=2022):
    """Fetch school data for a state from the Education Data Portal API."""

    # Map state abbreviations to FIPS codes
    fips_map = {
        'AL':1,'AK':2,'AZ':4,'AR':5,'CA':6,'CO':8,'CT':9,'DE':10,'FL':12,
        'GA':13,'HI':15,'ID':16,'IL':17,'IN':18,'IA':19,'KS':20,'KY':21,
        'LA':22,'ME':23,'MD':24,'MA':25,'MI':26,'MN':27,'MS':28,'MO':29,
        'MT':30,'NE':31,'NV':32,'NH':33,'NJ':34,'NM':35,'NY':36,'NC':37,
        'ND':38,'OH':39,'OK':40,'OR':41,'PA':42,'RI':44,'SC':45,'SD':46,
        'TN':47,'TX':48,'UT':49,'VT':50,'VA':51,'WA':53,'WV':54,'WI':55,
        'WY':56,'DC':11
    }

    fips = fips_map.get(state_abbr)
    if fips is None:
        return []

    url = f"https://educationdata.urban.org/api/v1/schools/ccd/directory/{year}/"
    params = {
        'fips': fips,
        'school_type': 1,  # Regular school
    }

    all_results = []
    page = 1

    while True:
        try:
            params['page'] = page
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()

            results = data.get('results', [])
            if not results:
                break

            for school in results:
                zip_code = str(school.get('zip_mailing', school.get('zip_location', ''))).split('-')[0].zfill(5)

                all_results.append({
                    'nces_school_id': school.get('ncessch', ''),
                    'school_name': school.get('school_name', ''),
                    'zip_code': zip_code,
                    'city': school.get('city_location', ''),
                    'state': state_abbr,
                    'school_level': school.get('school_level', ''),
                    'enrollment': school.get('enrollment', 0),
                    'teachers_fte': school.get('teachers_fte', 0),
                    'free_lunch': school.get('free_or_reduced_price_lunch', 0),
                    'charter': school.get('charter', 0),
                    'magnet': school.get('magnet', 0),
                    'title_i': school.get('title_i_eligible', 0),
                    'latitude': school.get('latitude', None),
                    'longitude': school.get('longitude', None),
                    'year': year
                })

            # Check if there are more pages
            if data.get('next') is None:
                break
            page += 1
            time.sleep(0.5)  # rate limit

        except Exception as e:
            print(f"  ⚠️ Error page {page} for {state_abbr}: {e}")
            break

    return all_results

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3. Fetch schools for all states
# MAGIC We fetch current year + 5 years ago for trend analysis.

# COMMAND ----------

# Fetch current year data
all_schools = []
for idx, state in enumerate(states):
    print(f"[{idx+1}/{len(states)}] Fetching {state}...")
    schools = fetch_schools_for_state(state, year=2022)
    all_schools.extend(schools)
    time.sleep(1)  # rate limit

print(f"\n✅ Total schools (2022): {len(all_schools)}")

# COMMAND ----------

# Fetch 5-year-ago data for trend comparison
schools_historical = []
for idx, state in enumerate(states):
    print(f"[{idx+1}/{len(states)}] Fetching {state} (2017)...")
    schools = fetch_schools_for_state(state, year=2017)
    schools_historical.extend(schools)
    time.sleep(1)

print(f"\n✅ Total schools (2017): {len(schools_historical)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4. Combine and calculate derived metrics

# COMMAND ----------

# Combine both years
all_schools_combined = all_schools + schools_historical
schools_df = pd.DataFrame(all_schools_combined)

# Calculate student-teacher ratio
schools_df['student_teacher_ratio'] = (
    schools_df['enrollment'].fillna(0) / schools_df['teachers_fte'].replace(0, pd.NA)
).round(1)

# Calculate free lunch percentage (proxy for economic diversity)
schools_df['free_lunch_pct'] = (
    schools_df['free_lunch'].fillna(0) / schools_df['enrollment'].replace(0, pd.NA) * 100
).round(1)

print(f"Total rows: {len(schools_df):,}")
print(f"\nBy year:")
print(schools_df['year'].value_counts())
print(f"\nSchool levels:")
print(schools_df['school_level'].value_counts())

# COMMAND ----------

# Write to Delta table
spark_schools = spark.createDataFrame(schools_df)
spark_schools.write.mode("overwrite").saveAsTable("dbt_hari.realestate_raw.raw_schools")
print("✅ raw_schools written to dbt_hari.realestate_raw")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT year, count(*) as school_count,
# MAGIC        count(distinct zip_code) as zip_count,
# MAGIC        round(avg(enrollment), 0) as avg_enrollment,
# MAGIC        round(avg(student_teacher_ratio), 1) as avg_student_teacher_ratio
# MAGIC FROM dbt_hari.realestate_raw.raw_schools
# MAGIC GROUP BY year
# MAGIC ORDER BY year;

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ School Data Ingestion Complete
# MAGIC
# MAGIC | Table | Description |
# MAGIC |-------|-------------|
# MAGIC | `realestate_raw.raw_schools` | NCES school data (2017 + 2022) with enrollment, ratios |
# MAGIC
# MAGIC **All 4 raw tables are now loaded:**
# MAGIC 1. ✅ `raw_home_values` — Zillow ZHVI
# MAGIC 2. ✅ `raw_rental_prices` — Zillow ZORI
# MAGIC 3. ✅ `raw_amenities` — OpenStreetMap
# MAGIC 4. ✅ `raw_schools` — NCES
# MAGIC
# MAGIC **Next:** Run `dbt build` to transform!
