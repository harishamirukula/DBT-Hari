-- ============================================================
-- INVESTMENT HOTSPOTS
-- ============================================================
-- Identifies the best ZIPs for real estate investment by
-- combining price appreciation with rental yield.
--
-- An ideal investment ZIP has:
--   - Strong price appreciation (equity growth)
--   - High rental yield (cash flow)
--   - Growing neighborhood (demand signal)
-- ============================================================

with market as (
    select * from {{ ref('market_intelligence') }}
)

select
    zip_code,
    city,
    state,
    metro,
    as_of_date,

    -- Price metrics
    home_value,
    price_change_1yr_pct,
    annual_appreciation_rate,
    price_trend,

    -- Yield metrics
    monthly_rent,
    gross_rental_yield,
    yield_tier,
    rent_growth_1yr_pct,

    -- Neighborhood & schools
    neighborhood_score,
    school_score,

    -- Investment score: heavier weight on yield + appreciation
    -- Yield: 35%, Appreciation: 35%, Neighborhood: 15%, Schools: 15%
    round(
        least(greatest(gross_rental_yield / 10 * 100, 0), 100) * 0.35 +
        least(greatest((annual_appreciation_rate + 10) / 20 * 100, 0), 100) * 0.35 +
        neighborhood_score * 0.15 +
        school_score * 0.15,
        1
    ) as investment_score,

    -- Cash-on-cash estimate (assuming 25% down, no expenses for simplicity)
    round(
        (monthly_rent * 12) / nullif(home_value * 0.25, 0) * 100,
        2
    ) as cash_on_cash_estimate,

    -- Buy signal
    case
        when gross_rental_yield >= 6
             and annual_appreciation_rate > 2
             and neighborhood_score >= 50
        then 'STRONG BUY'
        when gross_rental_yield >= 4
             and annual_appreciation_rate > 0
             and neighborhood_score >= 30
        then 'BUY'
        when gross_rental_yield >= 3
             and annual_appreciation_rate > -2
        then 'HOLD'
        else 'WATCH'
    end as investment_signal,

    -- Ranking within metro
    rank() over (
        partition by metro
        order by (
            least(greatest(gross_rental_yield / 10 * 100, 0), 100) * 0.35 +
            least(greatest((annual_appreciation_rate + 10) / 20 * 100, 0), 100) * 0.35 +
            neighborhood_score * 0.15 +
            school_score * 0.15
        ) desc
    ) as metro_investment_rank

from market
where monthly_rent is not null
  and gross_rental_yield is not null
