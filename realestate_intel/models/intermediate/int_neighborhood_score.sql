-- Neighborhood scoring per ZIP code
-- Scores each area on parks, shopping, entertainment, and dining
-- Uses percentile ranking within the dataset for normalization

with amenities as (
    select * from {{ ref('stg_amenities') }}
),

-- Count amenities by category per ZIP
amenity_counts as (
    select
        zip_code,
        city,
        state_name,
        sum(case when amenity_category = 'parks' then 1 else 0 end) as parks_count,
        sum(case when amenity_category = 'shopping' then 1 else 0 end) as shopping_count,
        sum(case when amenity_category = 'entertainment' then 1 else 0 end) as entertainment_count,
        sum(case when amenity_category = 'dining' then 1 else 0 end) as dining_count,
        count(*) as total_amenities
    from amenities
    group by zip_code, city, state_name
),

-- Calculate percentile ranks for each category (0-100 scale)
scored as (
    select
        zip_code,
        city,
        state_name,
        parks_count,
        shopping_count,
        entertainment_count,
        dining_count,
        total_amenities,

        -- Percentile rank scores (0-100)
        round(percent_rank() over (order by parks_count) * 100, 1) as parks_score,
        round(percent_rank() over (order by shopping_count) * 100, 1) as shopping_score,
        round(percent_rank() over (order by entertainment_count) * 100, 1) as entertainment_score,
        round(percent_rank() over (order by dining_count) * 100, 1) as dining_score,
        round(percent_rank() over (order by total_amenities) * 100, 1) as total_amenity_score

    from amenity_counts
)

select
    zip_code,
    city,
    state_name,

    -- Raw counts
    parks_count,
    shopping_count,
    entertainment_count,
    dining_count,
    total_amenities,

    -- Individual scores (0-100)
    parks_score,
    shopping_score,
    entertainment_score,
    dining_score,

    -- Composite neighborhood score (weighted average)
    -- Parks: 30%, Shopping: 20%, Entertainment: 25%, Dining: 25%
    round(
        parks_score * 0.30 +
        shopping_score * 0.20 +
        entertainment_score * 0.25 +
        dining_score * 0.25,
        1
    ) as neighborhood_score,

    -- Neighborhood tier
    case
        when round(parks_score * 0.30 + shopping_score * 0.20 +
                    entertainment_score * 0.25 + dining_score * 0.25, 1) >= 80 then 'excellent'
        when round(parks_score * 0.30 + shopping_score * 0.20 +
                    entertainment_score * 0.25 + dining_score * 0.25, 1) >= 60 then 'good'
        when round(parks_score * 0.30 + shopping_score * 0.20 +
                    entertainment_score * 0.25 + dining_score * 0.25, 1) >= 40 then 'average'
        when round(parks_score * 0.30 + shopping_score * 0.20 +
                    entertainment_score * 0.25 + dining_score * 0.25, 1) >= 20 then 'below_average'
        else 'poor'
    end as neighborhood_tier

from scored
