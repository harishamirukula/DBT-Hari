-- Rental yield analysis per ZIP code
-- Calculates gross rental yield (annual rent / home value)
-- With 30-day, 6-month, and 1-year yield trends

with rentals as (
    select * from {{ ref('stg_rental_prices') }}
),

home_values as (
    select * from {{ ref('stg_home_values') }}
),

-- Get latest date available in both datasets
latest_date as (
    select min(max_date) as ref_date from (
        select max(date) as max_date from rentals
        union all
        select max(date) as max_date from home_values
    )
),

-- Current rent and value
current_data as (
    select
        r.zip_code,
        r.city,
        r.state,
        r.metro,
        r.rental_price as current_rent,
        hv.home_value as current_value,
        r.date as as_of_date,
        -- Gross annual rental yield
        round((r.rental_price * 12) / nullif(hv.home_value, 0) * 100, 2) as current_yield
    from rentals r
    inner join latest_date ld on r.date = ld.ref_date
    inner join home_values hv
        on r.zip_code = hv.zip_code
        and r.date = hv.date
    where r.rental_price > 0 and hv.home_value > 0
),

-- Historical yields
historical_yields as (
    select
        cd.zip_code,

        -- 30 days ago yield
        round((r_30d.rental_price * 12) / nullif(hv_30d.home_value, 0) * 100, 2) as yield_30d_ago,
        r_30d.rental_price as rent_30d_ago,
        hv_30d.home_value as value_30d_ago,

        -- 6 months ago yield
        round((r_6m.rental_price * 12) / nullif(hv_6m.home_value, 0) * 100, 2) as yield_6m_ago,
        r_6m.rental_price as rent_6m_ago,
        hv_6m.home_value as value_6m_ago,

        -- 1 year ago yield
        round((r_1yr.rental_price * 12) / nullif(hv_1yr.home_value, 0) * 100, 2) as yield_1yr_ago,
        r_1yr.rental_price as rent_1yr_ago,
        hv_1yr.home_value as value_1yr_ago

    from current_data cd

    left join rentals r_30d on cd.zip_code = r_30d.zip_code
        and r_30d.date = add_months(cd.as_of_date, -1)
    left join home_values hv_30d on cd.zip_code = hv_30d.zip_code
        and hv_30d.date = add_months(cd.as_of_date, -1)

    left join rentals r_6m on cd.zip_code = r_6m.zip_code
        and r_6m.date = add_months(cd.as_of_date, -6)
    left join home_values hv_6m on cd.zip_code = hv_6m.zip_code
        and hv_6m.date = add_months(cd.as_of_date, -6)

    left join rentals r_1yr on cd.zip_code = r_1yr.zip_code
        and r_1yr.date = add_months(cd.as_of_date, -12)
    left join home_values hv_1yr on cd.zip_code = hv_1yr.zip_code
        and hv_1yr.date = add_months(cd.as_of_date, -12)
)

select
    cd.zip_code,
    cd.city,
    cd.state,
    cd.metro,
    cd.as_of_date,

    -- Current values
    cd.current_rent,
    cd.current_value,
    cd.current_yield,

    -- Annual rent
    round(cd.current_rent * 12, 0) as annual_rent,

    -- Historical yields
    hy.yield_30d_ago,
    hy.yield_6m_ago,
    hy.yield_1yr_ago,

    -- Yield changes (basis points)
    round((cd.current_yield - hy.yield_30d_ago) * 100, 0) as yield_change_30d_bps,
    round((cd.current_yield - hy.yield_6m_ago) * 100, 0) as yield_change_6m_bps,
    round((cd.current_yield - hy.yield_1yr_ago) * 100, 0) as yield_change_1yr_bps,

    -- Rent growth
    round((cd.current_rent - hy.rent_1yr_ago) / nullif(hy.rent_1yr_ago, 0) * 100, 2) as rent_growth_1yr_pct,

    -- Yield tier
    case
        when cd.current_yield >= 8 then 'premium'
        when cd.current_yield >= 6 then 'strong'
        when cd.current_yield >= 4 then 'average'
        when cd.current_yield >= 2 then 'below_average'
        else 'low'
    end as yield_tier,

    -- Yield trend
    case
        when cd.current_yield > hy.yield_1yr_ago then 'improving'
        when cd.current_yield < hy.yield_1yr_ago then 'compressing'
        else 'stable'
    end as yield_trend

from current_data cd
left join historical_yields hy on cd.zip_code = hy.zip_code
