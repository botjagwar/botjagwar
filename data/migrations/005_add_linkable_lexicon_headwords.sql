-- Migration 005: Expose the compact headword set used for definition links.

BEGIN;

CREATE OR REPLACE FUNCTION public.linkable_lexicon_headwords()
RETURNS TABLE (word text)
LANGUAGE sql
STABLE
PARALLEL SAFE
SET search_path = pg_catalog, public
AS $function$
    SELECT candidates.word
    FROM (
        SELECT DISTINCT source.word::text AS word
        FROM public.word AS source
        WHERE source.language = 'mg'
          AND source.part_of_speech IN ('ana', 'mat', 'mpam')
          AND char_length(source.word::text) > 4
          AND btrim(source.word::text) <> ''
    ) AS candidates
    ORDER BY candidates.word COLLATE "C";
$function$;

REVOKE ALL ON FUNCTION public.linkable_lexicon_headwords() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.linkable_lexicon_headwords() TO botjagwar;

NOTIFY pgrst, 'reload schema';

COMMIT;
