# Databricks notebook source
# MAGIC %md
# MAGIC # Real Estate Intelligence — Data Ingestion
# MAGIC ## Part 1: Zillow Home Values (ZHVI) & Rental Prices (ZORI)
# MAGIC
# MAGIC Downloads real Zillow CSV data, reshapes from wide to long format, and writes to Delta tables.
# MAGIC
# MAGIC **Run this notebook FIRST before running dbt.**

# COMMAND ----------

# MAGIC %md
# MAGIC ### Setup: Create the raw schema

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS dbt_hari.realestate_raw;

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1. Ingest Zillow Home Value Index (ZHVI)
# MAGIC Source: https://www.zillow.com/research/data/
# MAGIC - All Homes (SFR, Condo/Co-op), Smoothed, Seasonally Adjusted
# MAGIC - Monthly time series by ZIP code

# COMMAND ----------

import pandas as pd

# Download ZHVI data (All Homes, by ZIP code)
zhvi_url = "https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uf_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"

print("Downloading Zillow ZHVI data...")
zhvi_wide = pd.read_csv(zhvi_url)
print(f"Downloaded: {zhvi_wide.shape[0]} ZIP codes, {zhvi_wide.shape[1]} columns")

# Show the structure
zhvi_wide.head(3)

# COMMAND ----------

# Identify metadata columns vs date columns
meta_cols = ['RegionID', 'SizeRank', 'RegionName', 'RegionType', 'StateName', 'State', 'City', 'Metro', 'CountyName']
date_cols = [c for c in zhvi_wide.columns if c not in meta_cols]

print(f"Metadata columns: {len(meta_cols)}")
print(f"Date columns: {len(date_cols)}")
print(f"Date range: {date_cols[0]} to {date_cols[-1]}")

# COMMAND ----------

# Unpivot (melt) from wide to long format
zhvi_long = zhvi_wide.melt(
    id_vars=meta_cols,
    value_vars=date_cols,
    var_name='date',
    value_name='home_value'
)

# Clean up
zhvi_long['date'] = pd.to_datetime(zhvi_long['date'])
zhvi_long = zhvi_long.dropna(subset=['home_value'])  # drop months with no data
zhvi_long['RegionName'] = zhvi_long['RegionName'].astype(str).str.zfill(5)  # pad ZIP codes

# Rename columns to snake_case
zhvi_long = zhvi_long.rename(columns={
    'RegionID': 'region_id',
    'SizeRank': 'size_rank',
    'RegionName': 'zip_code',
    'RegionType': 'region_type',
    'StateName': 'state_name',
    'State': 'state',
    'City': 'city',
    'Metro': 'metro',
    'CountyName': 'county'
})

print(f"Long format: {zhvi_long.shape[0]:,} rows")
zhvi_long.head()

# COMMAND ----------

# Write to Delta table
spark_zhvi = spark.createDataFrame(zhvi_long)
spark_zhvi.write.mode("overwrite").saveAsTable("dbt_hari.realestate_raw.raw_home_values")
print("✅ raw_home_values written to dbt_hari.realestate_raw")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT count(*) as row_count,
# MAGIC        count(distinct zip_code) as zip_count,
# MAGIC        min(date) as earliest_date,
# MAGIC        max(date) as latest_date
# MAGIC FROM dbt_hari.realestate_raw.raw_home_values;

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2. Ingest Zillow Observed Rent Index (ZORI)
# MAGIC Source: https://www.zillow.com/research/data/
# MAGIC - All Homes + Multifamily, Smoothed, by ZIP code

# COMMAND ----------

# Download ZORI data
zori_url = "https://files.zillowstatic.com/research/public_csvs/zori/Zip_zori_uf_sfrcondomfr_sm_month.csv"

print("Downloading Zillow ZORI data...")
zori_wide = pd.read_csv(zori_url)
print(f"Downloaded: {zori_wide.shape[0]} ZIP codes, {zori_wide.shape[1]} columns")

zori_wide.head(3)

# COMMAND ----------

# Identify columns
zori_meta_cols = [c for c in meta_cols if c in zori_wide.columns]
zori_date_cols = [c for c in zori_wide.columns if c not in zori_meta_cols]

print(f"Metadata columns: {len(zori_meta_cols)}")
print(f"Date columns: {len(zori_date_cols)}")
print(f"Date range: {zori_date_cols[0]} to {zori_date_cols[-1]}")

# COMMAND ----------

# Unpivot ZORI
zori_long = zori_wide.melt(
    id_vars=zori_meta_cols,
    value_vars=zori_date_cols,
    var_name='date',
    value_name='rental_price'
)

zori_long['date'] = pd.to_datetime(zori_long['date'])
zori_long = zori_long.dropna(subset=['rental_price'])
zori_long['RegionName'] = zori_long['RegionName'].astype(str).str.zfill(5)

zori_long = zori_long.rename(columns={
    'RegionID': 'region_id',
    'SizeRank': 'size_rank',
    'RegionName': 'zip_code',
    'RegionType': 'region_type',
    'StateName': 'state_name',
    'State': 'state',
    'City': 'city',
    'Metro': 'metro',
    'CountyName': 'county'
})

print(f"Long format: {zori_long.shape[0]:,} rows")
zori_long.head()

# COMMAND ----------

# Write to Delta table
spark_zori = spark.createDataFrame(zori_long)
spark_zori.write.mode("overwrite").saveAsTable("dbt_hari.realestate_raw.raw_rental_prices")
print("✅ raw_rental_prices written to dbt_hari.realestate_raw")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT count(*) as row_count,
# MAGIC        count(distinct zip_code) as zip_count,
# MAGIC        min(date) as earliest_date,
# MAGIC        max(date) as latest_date
# MAGIC FROM dbt_hari.realestate_raw.raw_rental_prices;

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ Zillow Ingestion Complete
# MAGIC
# MAGIC | Table | Description |
# MAGIC |-------|-------------|
# MAGIC | `realestate_raw.raw_home_values` | ZHVI monthly home values by ZIP (long format) |
# MAGIC | `realestate_raw.raw_rental_prices` | ZORI monthly rental prices by ZIP (long format) |
# MAGIC
# MAGIC **Next:** Run `02_ingest_amenities.py` for OpenStreetMap data.
