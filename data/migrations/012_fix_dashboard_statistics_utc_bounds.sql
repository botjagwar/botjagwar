-- Migration 012: Keep dashboard period arithmetic independent of session DST.

BEGIN;

ALTER FUNCTION public.atlas_dashboard_statistics(integer)
    SET timezone = 'UTC';

NOTIFY pgrst, 'reload schema';

COMMIT;
