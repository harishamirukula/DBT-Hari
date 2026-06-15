-- Cleaned school data from NCES Education Data Portal
-- Includes 2017 and 2022 for 5-year trend analysis

with source as (
    select * from {{ source('realestate_raw', 'raw_schools') }}
),

cleaned as (
    select
        cast(nces_school_id as string) as nces_school_id,
        cast(school_name as string) as school_name,
        cast(zip_code as string) as zip_code,
        cast(city as string) as city,
        cast(state as string) as state,
        cast(school_level as int) as school_level,
        cast(enrollment as int) as enrollment,
        cast(teachers_fte as double) as teachers_fte,
        cast(free_lunch as int) as free_lunch,
        cast(charter as int) as charter,
        cast(magnet as int) as magnet,
        cast(title_i as int) as title_i,
        cast(latitude as double) as latitude,
        cast(longitude as double) as longitude,
        cast(year as int) as year,
        cast(student_teacher_ratio as double) as student_teacher_ratio,
        cast(free_lunch_pct as double) as free_lunch_pct,

        -- School level label
        case
            when school_level = 1 then 'Primary'
            when school_level = 2 then 'Middle'
            when school_level = 3 then 'High'
            when school_level = 4 then 'Other'
            else 'Unknown'
        end as school_level_name
    from source
    where zip_code is not null
      and enrollment is not null
      and enrollment > 0
)

select * from cleaned
