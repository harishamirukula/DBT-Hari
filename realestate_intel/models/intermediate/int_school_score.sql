-- School scoring per ZIP code
-- Aggregates school quality metrics and calculates 1-year and 5-year trends
-- Uses student-teacher ratio, enrollment stability, and economic diversity

with schools as (
    select * from {{ ref('stg_schools') }}
),

-- Current year (2022) school metrics by ZIP
current_schools as (
    select
        zip_code,
        city,
        state,

        count(*) as school_count,
        sum(enrollment) as total_enrollment,
        round(avg(student_teacher_ratio), 1) as avg_student_teacher_ratio,
        round(avg(free_lunch_pct), 1) as avg_free_lunch_pct,
        sum(case when charter = 1 then 1 else 0 end) as charter_count,
        sum(case when magnet = 1 then 1 else 0 end) as magnet_count,

        -- School level breakdown
        sum(case when school_level = 1 then 1 else 0 end) as primary_schools,
        sum(case when school_level = 2 then 1 else 0 end) as middle_schools,
        sum(case when school_level = 3 then 1 else 0 end) as high_schools

    from schools
    where year = 2022
    group by zip_code, city, state
),

-- Historical (2017) school metrics for trend
historical_schools as (
    select
        zip_code,
        count(*) as school_count_5yr,
        sum(enrollment) as total_enrollment_5yr,
        round(avg(student_teacher_ratio), 1) as avg_str_5yr,
        round(avg(free_lunch_pct), 1) as avg_flp_5yr
    from schools
    where year = 2017
    group by zip_code
),

-- Score calculation
scored as (
    select
        cs.zip_code,
        cs.city,
        cs.state,
        cs.school_count,
        cs.total_enrollment,
        cs.avg_student_teacher_ratio,
        cs.avg_free_lunch_pct,
        cs.charter_count,
        cs.magnet_count,
        cs.primary_schools,
        cs.middle_schools,
        cs.high_schools,

        -- 5-year trends
        hs.school_count_5yr,
        hs.total_enrollment_5yr,
        hs.avg_str_5yr as student_teacher_ratio_5yr_ago,

        -- Enrollment change (5yr)
        round((cs.total_enrollment - hs.total_enrollment_5yr)
              / nullif(hs.total_enrollment_5yr, 0) * 100, 1) as enrollment_change_5yr_pct,

        -- Student-teacher ratio change (lower is better, so negative change = improvement)
        round(cs.avg_student_teacher_ratio - hs.avg_str_5yr, 1) as str_change_5yr,

        -- Component scores (percentile-based, 0-100)
        -- Lower student-teacher ratio = higher score
        round(percent_rank() over (order by cs.avg_student_teacher_ratio desc) * 100, 1) as str_score,

        -- More school choices = higher score
        round(percent_rank() over (order by cs.school_count) * 100, 1) as choice_score,

        -- School level diversity (having all 3 levels is better)
        round(
            (case when cs.primary_schools > 0 then 33.3 else 0 end +
             case when cs.middle_schools > 0 then 33.3 else 0 end +
             case when cs.high_schools > 0 then 33.4 else 0 end),
            1
        ) as level_diversity_score

    from current_schools cs
    left join historical_schools hs on cs.zip_code = hs.zip_code
)

select
    zip_code,
    city,
    state,
    school_count,
    total_enrollment,
    avg_student_teacher_ratio,
    avg_free_lunch_pct,
    charter_count,
    magnet_count,
    primary_schools,
    middle_schools,
    high_schools,

    -- Trends
    enrollment_change_5yr_pct,
    str_change_5yr,
    student_teacher_ratio_5yr_ago,

    -- Component scores
    str_score,
    choice_score,
    level_diversity_score,

    -- Composite school score (weighted)
    -- Student-teacher ratio: 40%, School choice: 30%, Level diversity: 30%
    round(
        str_score * 0.40 +
        choice_score * 0.30 +
        level_diversity_score * 0.30,
        1
    ) as school_score,

    -- School quality tier
    case
        when round(str_score * 0.40 + choice_score * 0.30 + level_diversity_score * 0.30, 1) >= 80
            then 'excellent'
        when round(str_score * 0.40 + choice_score * 0.30 + level_diversity_score * 0.30, 1) >= 60
            then 'good'
        when round(str_score * 0.40 + choice_score * 0.30 + level_diversity_score * 0.30, 1) >= 40
            then 'average'
        when round(str_score * 0.40 + choice_score * 0.30 + level_diversity_score * 0.30, 1) >= 20
            then 'below_average'
        else 'poor'
    end as school_tier,

    -- Trend direction
    case
        when str_change_5yr < -1 and enrollment_change_5yr_pct > 0 then 'improving'
        when str_change_5yr > 1 and enrollment_change_5yr_pct < 0 then 'declining'
        else 'stable'
    end as school_trend

from scored
