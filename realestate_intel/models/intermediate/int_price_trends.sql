-- Price trend analysis per ZIP code
-- Calculates 30-day, 6-month, and 1-year appreciation rates
-- Uses the latest available date as the reference point

with home_values as (
    select * from {{ ref('stg_home_values') }}
),

-- Get the latest date in the dataset
latest_date as (
    select max(date) as max_date from home_values
),

-- Current values (latest month)
current_values as (
    select
        hv.zip_code,
        hv.city,
        hv.state,
        hv.state_name,
        hv.metro,
        hv.county,
        hv.home_value as current_value,
        hv.date as current_date
    from home_values hv
    inner join latest_date ld on hv.date = ld.max_date
),

-- Historical values at each lookback window
historical as (
    select
        cv.zip_code,
        cv.current_value,
        cv.current_date,

        -- 30 days ago (1 month)
        hv_30d.home_value as value_30d_ago,

        -- 6 months ago
        hv_6m.home_value as value_6m_ago,

        -- 1 year ago
        hv_1yr.home_value as value_1yr_ago

    from current_values cv

    -- Join 30-day lookback (closest to 1 month ago)
    left join home_values hv_30d
        on cv.zip_code = hv_30d.zip_code
        and hv_30d.date = add_months(cv.current_date, -1)

    -- Join 6-month lookback
    left join home_values hv_6m
        on cv.zip_code = hv_6m.zip_code
        and hv_6m.date = add_months(cv.current_date, -6)

    -- Join 1-year lookback
    left join home_values hv_1yr
        on cv.zip_code = hv_1yr.zip_code
        and hv_1yr.date = add_months(cv.current_date, -12)
)

select
    cv.zip_code,
    cv.city,
    cv.state,
    cv.state_name,
    cv.metro,
    cv.county,
    cv.current_date as as_of_date,

    -- Current value
    cv.current_value,

    -- Historical values
    h.value_30d_ago,
    h.value_6m_ago,
    h.value_1yr_ago,

    -- Percentage changes
    round((cv.current_value - h.value_30d_ago) / nullif(h.value_30d_ago, 0) * 100, 2) as pct_change_30d,
    round((cv.current_value - h.value_6m_ago) / nullif(h.value_6m_ago, 0) * 100, 2) as pct_change_6m,
    round((cv.current_value - h.value_1yr_ago) / nullif(h.value_1yr_ago, 0) * 100, 2) as pct_change_1yr,

    -- Dollar changes
    round(cv.current_value - h.value_30d_ago, 0) as dollar_change_30d,
    round(cv.current_value - h.value_6m_ago, 0) as dollar_change_6m,
    round(cv.current_value - h.value_1yr_ago, 0) as dollar_change_1yr,

    -- Annualized appreciation rate (from 1-year change)
    round((cv.current_value - h.value_1yr_ago) / nullif(h.value_1yr_ago, 0) * 100, 2) as annual_appreciation_rate,

    -- Trend direction
    case
        when (cv.current_value - h.value_1yr_ago) / nullif(h.value_1yr_ago, 0) > 0.05 then 'strong_appreciation'
        when (cv.current_value - h.value_1yr_ago) / nullif(h.value_1yr_ago, 0) > 0.01 then 'moderate_appreciation'
        when (cv.current_value - h.value_1yr_ago) / nullif(h.value_1yr_ago, 0) > -0.01 then 'stable'
        when (cv.current_value - h.value_1yr_ago) / nullif(h.value_1yr_ago, 0) > -0.05 then 'moderate_decline'
        else 'strong_decline'
    end as price_trend,

    -- Momentum: is short-term trend accelerating or decelerating?
    case
        when round((cv.current_value - h.value_30d_ago) / nullif(h.value_30d_ago, 0) * 100 * 12, 2) >
             round((cv.current_value - h.value_1yr_ago) / nullif(h.value_1yr_ago, 0) * 100, 2)
        then 'accelerating'
        else 'decelerating'
    end as price_momentum

from current_values cv
inner join historical h on cv.zip_code = h.zip_code
