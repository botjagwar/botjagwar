-- Migration 009: Backfill dashboard translation events recorded before migration 007.
--
-- events_malagasy_translation_created only captures activity once migration 007
-- is applied, so periods entirely before it (previous month, previous year, and
-- the pre-event part of year to date) report no translated languages even when
-- entries were translated. Reconstruct that history from immutable Malagasy
-- dictionary links, using word.date_changed as the best available timestamp,
-- then restore the append-only protection. ON CONFLICT keeps links already
-- captured by the triggers, and the dashboard counts distinct word IDs per
-- period, so backfilled approximations never inflate a language ranking.
--
-- The INSERT scans the dictionary join and may take several minutes on large
-- deployments; run it once when upgrading an existing production database.

BEGIN;

ALTER TABLE public.events_malagasy_translation_created
    DISABLE TRIGGER protect_malagasy_translation_events;

INSERT INTO public.events_malagasy_translation_created (
    word_id,
    definition_id,
    source_language,
    created_at,
    cause
)
SELECT DISTINCT
    links.word,
    links.definition,
    words.language,
    words.date_changed,
    'dictionary_insert'
FROM public.dictionary AS links
JOIN public.definitions AS definitions
  ON definitions.id = links.definition
JOIN public.word AS words
  ON words.id = links.word
WHERE definitions.definition_language = 'mg'
  AND words.language <> 'mg'
  AND words.date_changed IS NOT NULL
ON CONFLICT (word_id, definition_id, created_at, cause) DO NOTHING;

ALTER TABLE public.events_malagasy_translation_created
    ENABLE TRIGGER protect_malagasy_translation_events;

COMMIT;