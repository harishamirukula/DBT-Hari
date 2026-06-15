-- Cleaned rental price time series from Zillow ZORI
-- One row per ZIP code per month

with source as (
    select * from {{ source('realestate_raw', 'raw_rental_prices') }}
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
        cast(rental_price as double) as rental_price,
        cast(region_id as int) as region_id,
        cast(size_rank as int) as size_rank
    from source
    where rental_price is not null
      and rental_price > 0
      and zip_code is not null
)

select * from cleaned
