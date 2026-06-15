-- Cleaned neighborhood amenity records from OpenStreetMap
-- One row per amenity per ZIP code

with source as (
    select * from {{ source('realestate_raw', 'raw_amenities') }}
),

cleaned as (
    select
        cast(zip_code as string) as zip_code,
        cast(amenity_name as string) as amenity_name,
        cast(amenity_type as string) as amenity_type,
        cast(amenity_category as string) as amenity_category,
        cast(latitude as double) as latitude,
        cast(longitude as double) as longitude,
        cast(city as string) as city,
        cast(state_name as string) as state_name
    from source
    where zip_code is not null
      and amenity_category is not null
)

select * from cleaned
