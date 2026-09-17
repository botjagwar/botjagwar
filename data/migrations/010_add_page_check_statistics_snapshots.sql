-- Migration 010: Persist half-hourly page-check statistics for Atlas trends.

BEGIN;

CREATE TABLE public.page_check_statistics_snapshots (
    language character varying(10) NOT NULL,
    snapshot_at timestamp with time zone NOT NULL,
    period text NOT NULL CHECK (
        period IN (
            'today',
            'last_7_days',
            'current_week',
            'current_month',
            'last_3_months',
            'last_6_months'
        )
    ),
    generated_at timestamp with time zone NOT NULL,
    period_start timestamp with time zone NOT NULL,
    period_end timestamp with time zone NOT NULL,
    retention_limit integer NOT NULL CHECK (retention_limit > 0),
    retained_job_count integer NOT NULL CHECK (
        retained_job_count >= 0 AND retained_job_count <= retention_limit
    ),
    job_count integer NOT NULL CHECK (job_count >= 0),
    checked_count integer NOT NULL CHECK (
        checked_count >= 0 AND checked_count <= job_count
    ),
    assessable_count integer NOT NULL CHECK (
        assessable_count >= 0 AND assessable_count <= checked_count
    ),
    good_count integer NOT NULL CHECK (good_count >= 0),
    fixed_count integer NOT NULL CHECK (fixed_count >= 0),
    unverifiable_count integer NOT NULL CHECK (unverifiable_count >= 0),
    error_count integer NOT NULL CHECK (error_count >= 0),
    good_percentage numeric(5, 1) CHECK (
        good_percentage IS NULL OR good_percentage BETWEEN 0 AND 100
    ),
    grade character(1) CHECK (grade IS NULL OR grade IN ('A', 'B', 'C', 'D', 'E')),
    PRIMARY KEY (language, snapshot_at, period),
    CHECK (period_start <= period_end),
    CHECK (generated_at >= snapshot_at AND generated_at < snapshot_at + interval '30 minutes'),
    CHECK (
        extract(minute FROM snapshot_at AT TIME ZONE 'UTC') IN (0, 30)
        AND extract(second FROM snapshot_at AT TIME ZONE 'UTC') = 0
    ),
    CHECK (checked_count = good_count + fixed_count + unverifiable_count + error_count),
    CHECK (assessable_count = good_count + fixed_count),
    CHECK (
        (assessable_count = 0 AND good_percentage IS NULL AND grade IS NULL)
        OR (assessable_count > 0 AND good_percentage IS NOT NULL AND grade IS NOT NULL)
    )
);

ALTER TABLE public.page_check_statistics_snapshots OWNER TO botjagwar;

CREATE INDEX page_check_statistics_snapshots_history_idx
    ON public.page_check_statistics_snapshots (language, period, snapshot_at);

GRANT SELECT, INSERT, UPDATE ON public.page_check_statistics_snapshots TO botjagwar;

CREATE OR REPLACE FUNCTION public.page_check_score_history(
    p_language text,
    p_period text,
    p_max_points integer DEFAULT 480
)
RETURNS TABLE (
    snapshot_at timestamp with time zone,
    generated_at timestamp with time zone,
    good_percentage numeric,
    assessable_count integer,
    retained_job_count integer,
    retention_limit integer
)
LANGUAGE plpgsql
STABLE
PARALLEL SAFE
SET search_path = pg_catalog, public
AS $function$
DECLARE
    v_as_of timestamp with time zone := statement_timestamp();
    v_period_start timestamp with time zone;
BEGIN
    IF p_max_points IS NULL OR p_max_points < 2 OR p_max_points > 2000 THEN
        RAISE EXCEPTION 'p_max_points must be between 2 and 2000'
            USING ERRCODE = '22023';
    END IF;

    v_period_start := CASE p_period
        WHEN 'today' THEN
            date_trunc('day', v_as_of AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
        WHEN 'last_7_days' THEN
            ((v_as_of AT TIME ZONE 'UTC') - interval '7 days') AT TIME ZONE 'UTC'
        WHEN 'current_week' THEN
            date_trunc('week', v_as_of AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
        WHEN 'current_month' THEN
            date_trunc('month', v_as_of AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
        WHEN 'last_3_months' THEN
            ((v_as_of AT TIME ZONE 'UTC') - interval '3 months') AT TIME ZONE 'UTC'
        WHEN 'last_6_months' THEN
            ((v_as_of AT TIME ZONE 'UTC') - interval '6 months') AT TIME ZONE 'UTC'
        ELSE NULL
    END;

    IF v_period_start IS NULL THEN
        RAISE EXCEPTION 'Unsupported page-check statistics period: %', p_period
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    WITH filtered AS (
        SELECT
            snapshots.snapshot_at,
            snapshots.generated_at,
            snapshots.good_percentage,
            snapshots.assessable_count,
            snapshots.retained_job_count,
            snapshots.retention_limit,
            count(*) OVER () AS total_count
        FROM public.page_check_statistics_snapshots AS snapshots
        WHERE snapshots.language = p_language
          AND snapshots.period = p_period
          AND snapshots.snapshot_at >= v_period_start
          AND snapshots.snapshot_at <= v_as_of
    ), bucketed AS (
        SELECT
            filtered.*,
            ntile(least(p_max_points, filtered.total_count::integer)) OVER (
                ORDER BY filtered.snapshot_at
            ) AS sample_bucket
        FROM filtered
    ), sampled AS (
        SELECT DISTINCT ON (bucketed.sample_bucket)
            bucketed.snapshot_at,
            bucketed.generated_at,
            bucketed.good_percentage,
            bucketed.assessable_count,
            bucketed.retained_job_count,
            bucketed.retention_limit,
            bucketed.sample_bucket
        FROM bucketed
        ORDER BY bucketed.sample_bucket, bucketed.snapshot_at DESC
    )
    SELECT
        sampled.snapshot_at,
        sampled.generated_at,
        sampled.good_percentage,
        sampled.assessable_count,
        sampled.retained_job_count,
        sampled.retention_limit
    FROM sampled
    ORDER BY sampled.snapshot_at;
END;
$function$;

ALTER FUNCTION public.page_check_score_history(text, text, integer) OWNER TO botjagwar;
REVOKE ALL ON FUNCTION public.page_check_score_history(text, text, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.page_check_score_history(text, text, integer) TO botjagwar;

NOTIFY pgrst, 'reload schema';

COMMIT;
