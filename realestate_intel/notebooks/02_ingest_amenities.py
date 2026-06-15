# Databricks notebook source
# MAGIC %md
# MAGIC # Real Estate Intelligence — Data Ingestion
# MAGIC ## Part 2: OpenStreetMap Neighborhood Amenities
# MAGIC
# MAGIC Queries the Overpass API for parks, shopping, entertainment, and dining
# MAGIC near each ZIP code, then writes to a Delta table.
# MAGIC
# MAGIC **Rate limits:** Overpass API allows ~10K requests/day. This notebook
# MAGIC queries by unique cities in the Zillow data (not all 30K ZIPs).

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1. Get unique cities from our Zillow data

# COMMAND ----------

import requests
import pandas as pd
import time
from pyspark.sql import Row

# Get the unique city/state combos from our home values data
cities_df = spark.sql("""
    SELECT DISTINCT city, state, state_name,
           collect_set(zip_code) as zip_codes,
           count(distinct zip_code) as zip_count
    FROM dbt_hari.realestate_raw.raw_home_values
    WHERE city IS NOT NULL AND state IS NOT NULL
    GROUP BY city, state, state_name
    ORDER BY zip_count DESC
""").toPandas()

print(f"Total unique cities: {len(cities_df)}")
cities_df.head(10)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2. Define Overpass API queries
# MAGIC We query 4 amenity categories:
# MAGIC - **Parks**: leisure=park, leisure=garden, leisure=nature_reserve
# MAGIC - **Shopping**: shop=supermarket, shop=mall, shop=department_store, amenity=marketplace
# MAGIC - **Entertainment**: amenity=cinema, amenity=theatre, leisure=fitness_centre, tourism=museum
# MAGIC - **Dining**: amenity=restaurant, amenity=cafe, amenity=fast_food, amenity=bar

# COMMAND ----------

def query_amenities_for_city(city, state_name):
    """Query Overpass API for amenity counts in a city."""

    overpass_url = "https://overpass-api.de/api/interpreter"

    # Query all amenity types in one call
    query = f"""
    [out:json][timeout:30];
    area["name"="{city}"]["admin_level"~"[6-8]"]["is_in:state"="{state_name}"]->.searchArea;
    (
      // Parks & Recreation
      node["leisure"="park"](area.searchArea);
      way["leisure"="park"](area.searchArea);
      node["leisure"="garden"](area.searchArea);
      way["leisure"="garden"](area.searchArea);
      node["leisure"="nature_reserve"](area.searchArea);
      way["leisure"="nature_reserve"](area.searchArea);

      // Shopping
      node["shop"="supermarket"](area.searchArea);
      node["shop"="mall"](area.searchArea);
      node["shop"="department_store"](area.searchArea);
      node["amenity"="marketplace"](area.searchArea);

      // Entertainment
      node["amenity"="cinema"](area.searchArea);
      node["amenity"="theatre"](area.searchArea);
      node["leisure"="fitness_centre"](area.searchArea);
      node["tourism"="museum"](area.searchArea);

      // Dining
      node["amenity"="restaurant"](area.searchArea);
      node["amenity"="cafe"](area.searchArea);
      node["amenity"="bar"](area.searchArea);
    );
    out tags center;
    """

    try:
        response = requests.get(overpass_url, params={"data": query}, timeout=60)
        response.raise_for_status()
        data = response.json()

        results = []
        for element in data.get('elements', []):
            tags = element.get('tags', {})

            # Determine amenity type and category
            if tags.get('leisure') in ('park', 'garden', 'nature_reserve'):
                category = 'parks'
                amenity_type = tags.get('leisure')
            elif tags.get('shop') or tags.get('amenity') == 'marketplace':
                category = 'shopping'
                amenity_type = tags.get('shop', 'marketplace')
            elif tags.get('amenity') in ('cinema', 'theatre') or \
                 tags.get('leisure') == 'fitness_centre' or \
                 tags.get('tourism') == 'museum':
                category = 'entertainment'
                amenity_type = tags.get('amenity') or tags.get('leisure') or tags.get('tourism')
            elif tags.get('amenity') in ('restaurant', 'cafe', 'fast_food', 'bar'):
                category = 'dining'
                amenity_type = tags.get('amenity')
            else:
                continue

            lat = element.get('lat') or element.get('center', {}).get('lat')
            lon = element.get('lon') or element.get('center', {}).get('lon')

            results.append({
                'amenity_name': tags.get('name', 'unnamed'),
                'amenity_type': amenity_type,
                'amenity_category': category,
                'latitude': lat,
                'longitude': lon,
                'city': city,
                'state_name': state_name
            })

        return results

    except Exception as e:
        print(f"  ⚠️ Error for {city}, {state_name}: {e}")
        return []

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3. Query top cities (by ZIP count)
# MAGIC We query the top 100 cities to stay within API limits.
# MAGIC Scale up by re-running with a larger limit.

# COMMAND ----------

# Query top N cities (adjust based on time/rate limits)
TOP_N = 100  # increase to cover more cities
top_cities = cities_df.head(TOP_N)

all_amenities = []
for idx, row in top_cities.iterrows():
    city = row['city']
    state = row['state_name']

    print(f"[{idx+1}/{TOP_N}] Querying {city}, {state}...")
    amenities = query_amenities_for_city(city, state)
    all_amenities.extend(amenities)

    # Rate limit: 1 request per 2 seconds
    time.sleep(2)

print(f"\n✅ Total amenities found: {len(all_amenities)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4. Map amenities to ZIP codes using Zillow's city mapping

# COMMAND ----------

# Create amenity dataframe
amenities_df = pd.DataFrame(all_amenities)

if len(amenities_df) > 0:
    # Get ZIP-to-city mapping from Zillow data
    zip_city_map = spark.sql("""
        SELECT DISTINCT zip_code, city, state_name
        FROM dbt_hari.realestate_raw.raw_home_values
        WHERE city IS NOT NULL
    """).toPandas()

    # Join amenities to ZIP codes through city
    amenities_with_zip = amenities_df.merge(
        zip_city_map,
        on=['city', 'state_name'],
        how='inner'
    )

    # Select final columns
    amenities_final = amenities_with_zip[[
        'zip_code', 'amenity_name', 'amenity_type', 'amenity_category',
        'latitude', 'longitude', 'city', 'state_name'
    ]]

    print(f"Amenities mapped to ZIPs: {len(amenities_final):,} rows")
    print(f"ZIP codes covered: {amenities_final['zip_code'].nunique()}")
    print(f"\nBy category:")
    print(amenities_final['amenity_category'].value_counts())
else:
    print("⚠️ No amenities found. Check API connectivity.")

# COMMAND ----------

# Write to Delta table
if len(amenities_final) > 0:
    spark_amenities = spark.createDataFrame(amenities_final)
    spark_amenities.write.mode("overwrite").saveAsTable("dbt_hari.realestate_raw.raw_amenities")
    print("✅ raw_amenities written to dbt_hari.realestate_raw")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT amenity_category, count(*) as count, count(distinct zip_code) as zips_covered
# MAGIC FROM dbt_hari.realestate_raw.raw_amenities
# MAGIC GROUP BY amenity_category
# MAGIC ORDER BY count DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ Amenities Ingestion Complete
# MAGIC
# MAGIC | Table | Description |
# MAGIC |-------|-------------|
# MAGIC | `realestate_raw.raw_amenities` | OSM amenities mapped to ZIP codes |
# MAGIC
# MAGIC **Categories:** parks, shopping, entertainment, dining
# MAGIC
# MAGIC **Next:** Run `03_ingest_schools.py` for school ratings data.
