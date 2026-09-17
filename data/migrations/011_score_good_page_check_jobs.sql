-- Migration 011: Score page checks as good jobs divided by all jobs.

BEGIN;

DO $function$
DECLARE
    score_constraint record;
BEGIN
    FOR score_constraint IN
        SELECT constraints.conname
        FROM pg_constraint AS constraints
        WHERE constraints.conrelid = 'public.page_check_statistics_snapshots'::regclass
          AND constraints.contype = 'c'
          AND pg_get_constraintdef(constraints.oid) LIKE '%assessable_count%'
          AND pg_get_constraintdef(constraints.oid) LIKE '%good_percentage IS NULL%'
          AND pg_get_constraintdef(constraints.oid) LIKE '%grade IS NULL%'
    LOOP
        EXECUTE format(
            'ALTER TABLE public.page_check_statistics_snapshots DROP CONSTRAINT %I',
            score_constraint.conname
        );
    END LOOP;
END;
$function$;

WITH recalculated AS (
    SELECT
        language,
        snapshot_at,
        period,
        CASE
            WHEN job_count = 0 THEN NULL
            ELSE round(good_count * 100.0 / job_count, 1)
        END AS percentage
    FROM public.page_check_statistics_snapshots
)
UPDATE public.page_check_statistics_snapshots AS snapshots
SET
    good_percentage = recalculated.percentage,
    grade = CASE
        WHEN recalculated.percentage IS NULL THEN NULL
        WHEN recalculated.percentage >= 90 THEN 'A'
        WHEN recalculated.percentage >= 80 THEN 'B'
        WHEN recalculated.percentage >= 70 THEN 'C'
        WHEN recalculated.percentage >= 60 THEN 'D'
        ELSE 'E'
    END
FROM recalculated
WHERE snapshots.language = recalculated.language
  AND snapshots.snapshot_at = recalculated.snapshot_at
  AND snapshots.period = recalculated.period;

ALTER TABLE public.page_check_statistics_snapshots
    ADD CONSTRAINT page_check_statistics_snapshots_job_score_check CHECK (
        (job_count = 0 AND good_percentage IS NULL AND grade IS NULL)
        OR (job_count > 0 AND good_percentage IS NOT NULL AND grade IS NOT NULL)
    );

COMMIT;
