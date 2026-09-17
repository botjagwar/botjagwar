-- Migration 008: Add the Atlas dashboard statistics materialized view.
--
-- Snapshot of the atlas_dashboard_statistics RPC, refreshed every five
-- minutes by the dashboard cron job. The unique index on period enables
-- concurrent refreshes without blocking readers.

BEGIN;

CREATE MATERIALIZED VIEW public.atlas_dashboard_statistics_mv AS
    SELECT * FROM public.atlas_dashboard_statistics(8);

ALTER MATERIALIZED VIEW public.atlas_dashboard_statistics_mv OWNER TO botjagwar;

CREATE UNIQUE INDEX atlas_dashboard_statistics_mv_period_idx
    ON public.atlas_dashboard_statistics_mv (period);

GRANT SELECT ON public.atlas_dashboard_statistics_mv TO botjagwar;

NOTIFY pgrst, 'reload schema';

COMMIT;