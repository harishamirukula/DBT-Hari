-- Cleaned home value time series from Zillow ZHVI
-- One row per ZIP code per month

with source as (
    select * from {{ source('realestate_raw', 'raw_home_values') }}
),

cleaned as (
    select
        cast(zip_code as string) as zip_code,
        cast(city as string) as city,
        cast(state as string) as state,
        cast(state_name as string) as state_name,
        cast(metro as string) as metro,
        cast(county as string) as county,
        cast(date as date) as date,
        cast(home_value as double) as home_value,
        cast(region_id as int) as region_id,
        cast(size_rank as int) as size_rank
    from source
    where home_value is not null
      and home_value > 0
      and zip_code is not null
)

select * from cleaned
