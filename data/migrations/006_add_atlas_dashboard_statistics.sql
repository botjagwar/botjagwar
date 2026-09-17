-- Migration 006: Add live Atlas entry and translation statistics.

BEGIN;

ALTER TABLE public.word
    ALTER COLUMN date_changed SET DEFAULT now();

CREATE OR REPLACE FUNCTION public.atlas_dashboard_statistics(
    p_language_limit integer DEFAULT 8
)
RETURNS TABLE (
    period text,
    period_start timestamp with time zone,
    period_end timestamp with time zone,
    entry_count bigint,
    translated_languages jsonb,
    generated_at timestamp with time zone,
    missing_timestamp_count bigint
)
LANGUAGE sql
STABLE
PARALLEL SAFE
SET search_path = pg_catalog, public
AS $function$
    WITH clock AS (
        SELECT
            current_timestamp AS as_of,
            date_trunc('week', current_timestamp AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' AS week_start,
            date_trunc('month', current_timestamp AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' AS month_start,
            date_trunc('year', current_timestamp AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' AS year_start,
            least(greatest(COALESCE(p_language_limit, 8), 1), 25) AS language_limit
    ), bounds (period, sort_order, period_start, period_end) AS (
        SELECT 'last_day', 1, as_of - interval '1 day', as_of FROM clock
        UNION ALL
        SELECT 'last_7_days', 2, as_of - interval '7 days', as_of FROM clock
        UNION ALL
        SELECT 'last_week', 3, week_start - interval '1 week', week_start FROM clock
        UNION ALL
        SELECT 'last_month', 4, month_start - interval '1 month', month_start FROM clock
        UNION ALL
        SELECT 'year_to_date', 5, year_start, as_of FROM clock
        UNION ALL
        SELECT 'last_year', 6, year_start - interval '1 year', year_start FROM clock
    ), entry_counts AS (
        SELECT bounds.period, count(words.id) AS entry_count
        FROM bounds
        LEFT JOIN public.word AS words
          ON words.date_changed >= bounds.period_start
         AND words.date_changed < bounds.period_end
        GROUP BY bounds.period
    ), translated_counts AS (
        SELECT
            bounds.period,
            words.language,
            languages.english_name,
            languages.malagasy_name,
            count(*) AS translated_entries
        FROM bounds
        JOIN public.word AS words
          ON words.date_changed >= bounds.period_start
         AND words.date_changed < bounds.period_end
         AND words.language <> 'mg'
        LEFT JOIN public.language AS languages ON languages.iso_code = words.language
        WHERE EXISTS (
            SELECT 1
            FROM public.dictionary AS links
            JOIN public.definitions AS definitions ON definitions.id = links.definition
            WHERE links.word = words.id
              AND definitions.definition_language = 'mg'
        )
        GROUP BY bounds.period, words.language, languages.english_name, languages.malagasy_name
    ), ranked_languages AS (
        SELECT
            translated_counts.*,
            row_number() OVER (
                PARTITION BY translated_counts.period
                ORDER BY translated_counts.translated_entries DESC, translated_counts.language
            ) AS language_rank
        FROM translated_counts
    ), language_lists AS (
        SELECT
            bounds.period,
            COALESCE(
                jsonb_agg(
                    jsonb_build_object(
                        'language', ranked_languages.language,
                        'english_name', ranked_languages.english_name,
                        'malagasy_name', ranked_languages.malagasy_name,
                        'translated_entries', ranked_languages.translated_entries
                    ) ORDER BY ranked_languages.language_rank
                ) FILTER (WHERE ranked_languages.language_rank <= clock.language_limit),
                '[]'::jsonb
            ) AS translated_languages
        FROM bounds
        CROSS JOIN clock
        LEFT JOIN ranked_languages ON ranked_languages.period = bounds.period
        GROUP BY bounds.period
    ), missing_timestamps AS (
        SELECT count(*) AS missing_timestamp_count
        FROM public.word
        WHERE date_changed IS NULL
    )
    SELECT
        bounds.period,
        bounds.period_start,
        bounds.period_end,
        entry_counts.entry_count,
        language_lists.translated_languages,
        clock.as_of AS generated_at,
        missing_timestamps.missing_timestamp_count
    FROM bounds
    JOIN entry_counts ON entry_counts.period = bounds.period
    JOIN language_lists ON language_lists.period = bounds.period
    CROSS JOIN clock
    CROSS JOIN missing_timestamps
    ORDER BY bounds.sort_order;
$function$;

REVOKE ALL ON FUNCTION public.atlas_dashboard_statistics(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.atlas_dashboard_statistics(integer) TO botjagwar;

NOTIFY pgrst, 'reload schema';

COMMIT;
