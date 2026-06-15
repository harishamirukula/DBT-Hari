-- ============================================================
-- AREA COMPARISON: Metro-Level Summary
-- ============================================================
-- Aggregates ZIP-level data to metro area for city-vs-city
-- comparison. One row per metro area.
--
-- Use case: "Compare Dallas vs Austin vs Denver for relocation"
-- ============================================================

with market as (
    select * from {{ ref('market_intelligence') }}
    where metro is not null
)

select
    metro,
    max(state) as state,
    max(as_of_date) as as_of_date,

    -- Coverage
    count(distinct zip_code) as zip_count,

    -- Price summary
    round(avg(home_value), 0) as avg_home_value,
    round(min(home_value), 0) as min_home_value,
    round(max(home_value), 0) as max_home_value,
    round(percentile_approx(home_value, 0.5), 0) as median_home_value,
    round(avg(price_change_1yr_pct), 2) as avg_price_change_1yr_pct,
    round(avg(annual_appreciation_rate), 2) as avg_appreciation_rate,

    -- Rent summary
    round(avg(monthly_rent), 0) as avg_monthly_rent,
    round(avg(gross_rental_yield), 2) as avg_rental_yield,
    round(avg(rent_growth_1yr_pct), 2) as avg_rent_growth_1yr_pct,

    -- Affordability ratio (home value / annual rent)
    round(avg(home_value) / nullif(avg(monthly_rent * 12), 0), 1) as price_to_rent_ratio,

    -- Neighborhood summary
    round(avg(neighborhood_score), 1) as avg_neighborhood_score,
    round(avg(parks_score), 1) as avg_parks_score,
    round(avg(shopping_score), 1) as avg_shopping_score,
    round(avg(entertainment_score), 1) as avg_entertainment_score,
    round(avg(dining_score), 1) as avg_dining_score,

    -- School summary
    round(avg(school_score), 1) as avg_school_score,
    sum(school_count) as total_schools,
    round(avg(avg_student_teacher_ratio), 1) as avg_student_teacher_ratio,

    -- Livability summary
    round(avg(livability_score), 1) as avg_livability_score,

    -- Distribution of livability tiers
    sum(case when livability_tier = 'A - Premium' then 1 else 0 end) as premium_zips,
    sum(case when livability_tier = 'B - Good' then 1 else 0 end) as good_zips,
    sum(case when livability_tier = 'C - Average' then 1 else 0 end) as average_zips,

    -- Market health indicators
    round(
        sum(case when price_trend in ('strong_appreciation', 'moderate_appreciation') then 1 else 0 end)
        * 100.0 / count(*),
        1
    ) as pct_appreciating,

    round(
        sum(case when price_trend in ('strong_decline', 'moderate_decline') then 1 else 0 end)
        * 100.0 / count(*),
        1
    ) as pct_declining

from market
group by metro
