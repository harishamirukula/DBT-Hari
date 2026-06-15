-- ============================================================
-- MARKET INTELLIGENCE: The Primary Buyer Search Table
-- ============================================================
-- Combines price trends, rental yield, neighborhood amenities,
-- and school quality into one searchable view per ZIP code.
--
-- This is the main table a home buyer would query:
--   "Show me ZIPs with appreciating prices, good schools,
--    and a neighborhood score above 70"
-- ============================================================

with price_trends as (
    select * from {{ ref('int_price_trends') }}
),

rental_yield as (
    select * from {{ ref('int_rental_yield') }}
),

neighborhood as (
    select * from {{ ref('int_neighborhood_score') }}
),

schools as (
    select * from {{ ref('int_school_score') }}
)

select
    -- Location
    pt.zip_code,
    pt.city,
    pt.state,
    pt.state_name,
    pt.metro,
    pt.county,
    pt.as_of_date,

    -- ========== PRICE TRENDS ==========
    pt.current_value as home_value,
    pt.pct_change_30d as price_change_30d_pct,
    pt.pct_change_6m as price_change_6m_pct,
    pt.pct_change_1yr as price_change_1yr_pct,
    pt.dollar_change_1yr as price_change_1yr_dollars,
    pt.annual_appreciation_rate,
    pt.price_trend,
    pt.price_momentum,

    -- ========== RENTAL YIELD ==========
    ry.current_rent as monthly_rent,
    ry.annual_rent,
    ry.current_yield as gross_rental_yield,
    ry.yield_change_1yr_bps as yield_change_1yr,
    ry.rent_growth_1yr_pct,
    ry.yield_tier,
    ry.yield_trend,

    -- ========== NEIGHBORHOOD ==========
    coalesce(ns.parks_count, 0) as parks_count,
    coalesce(ns.shopping_count, 0) as shopping_count,
    coalesce(ns.entertainment_count, 0) as entertainment_count,
    coalesce(ns.dining_count, 0) as dining_count,
    coalesce(ns.parks_score, 0) as parks_score,
    coalesce(ns.shopping_score, 0) as shopping_score,
    coalesce(ns.entertainment_score, 0) as entertainment_score,
    coalesce(ns.dining_score, 0) as dining_score,
    coalesce(ns.neighborhood_score, 0) as neighborhood_score,
    coalesce(ns.neighborhood_tier, 'no_data') as neighborhood_tier,

    -- ========== SCHOOLS ==========
    coalesce(sc.school_count, 0) as school_count,
    coalesce(sc.total_enrollment, 0) as total_enrollment,
    sc.avg_student_teacher_ratio,
    coalesce(sc.primary_schools, 0) as primary_schools,
    coalesce(sc.middle_schools, 0) as middle_schools,
    coalesce(sc.high_schools, 0) as high_schools,
    sc.enrollment_change_5yr_pct,
    coalesce(sc.school_score, 0) as school_score,
    coalesce(sc.school_tier, 'no_data') as school_tier,
    coalesce(sc.school_trend, 'no_data') as school_trend,

    -- ========== COMPOSITE LIVABILITY SCORE ==========
    -- Weighted: Price trend 25%, Rental yield 20%, Neighborhood 30%, Schools 25%
    round(
        -- Price: map appreciation rate to 0-100 (capped at ±10%)
        least(greatest((pt.annual_appreciation_rate + 10) / 20 * 100, 0), 100) * 0.25 +

        -- Yield: map yield to 0-100 (0-10% range)
        least(greatest(coalesce(ry.current_yield, 0) / 10 * 100, 0), 100) * 0.20 +

        -- Neighborhood score (already 0-100)
        coalesce(ns.neighborhood_score, 50) * 0.30 +

        -- School score (already 0-100)
        coalesce(sc.school_score, 50) * 0.25,
        1
    ) as livability_score,

    -- Livability tier
    case
        when round(
            least(greatest((pt.annual_appreciation_rate + 10) / 20 * 100, 0), 100) * 0.25 +
            least(greatest(coalesce(ry.current_yield, 0) / 10 * 100, 0), 100) * 0.20 +
            coalesce(ns.neighborhood_score, 50) * 0.30 +
            coalesce(sc.school_score, 50) * 0.25, 1
        ) >= 80 then 'A - Premium'
        when round(
            least(greatest((pt.annual_appreciation_rate + 10) / 20 * 100, 0), 100) * 0.25 +
            least(greatest(coalesce(ry.current_yield, 0) / 10 * 100, 0), 100) * 0.20 +
            coalesce(ns.neighborhood_score, 50) * 0.30 +
            coalesce(sc.school_score, 50) * 0.25, 1
        ) >= 60 then 'B - Good'
        when round(
            least(greatest((pt.annual_appreciation_rate + 10) / 20 * 100, 0), 100) * 0.25 +
            least(greatest(coalesce(ry.current_yield, 0) / 10 * 100, 0), 100) * 0.20 +
            coalesce(ns.neighborhood_score, 50) * 0.30 +
            coalesce(sc.school_score, 50) * 0.25, 1
        ) >= 40 then 'C - Average'
        when round(
            least(greatest((pt.annual_appreciation_rate + 10) / 20 * 100, 0), 100) * 0.25 +
            least(greatest(coalesce(ry.current_yield, 0) / 10 * 100, 0), 100) * 0.20 +
            coalesce(ns.neighborhood_score, 50) * 0.30 +
            coalesce(sc.school_score, 50) * 0.25, 1
        ) >= 20 then 'D - Below Average'
        else 'F - Poor'
    end as livability_tier,

    -- Metro ranking
    rank() over (
        partition by pt.metro
        order by round(
            least(greatest((pt.annual_appreciation_rate + 10) / 20 * 100, 0), 100) * 0.25 +
            least(greatest(coalesce(ry.current_yield, 0) / 10 * 100, 0), 100) * 0.20 +
            coalesce(ns.neighborhood_score, 50) * 0.30 +
            coalesce(sc.school_score, 50) * 0.25, 1
        ) desc
    ) as metro_rank

from price_trends pt
left join rental_yield ry on pt.zip_code = ry.zip_code
left join neighborhood ns on pt.zip_code = ns.zip_code
left join schools sc on pt.zip_code = sc.zip_code
