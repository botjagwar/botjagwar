-- Migration 004: Track successful materialized-view refresh timestamps.

BEGIN;

CREATE TABLE IF NOT EXISTS public.materialized_view_refresh_status (
    schema_name text NOT NULL,
    view_name text NOT NULL,
    refreshed_at timestamp with time zone NOT NULL DEFAULT now(),
    PRIMARY KEY (schema_name, view_name)
);

GRANT SELECT, INSERT, UPDATE ON public.materialized_view_refresh_status TO botjagwar;
NOTIFY pgrst, 'reload schema';

COMMIT;
