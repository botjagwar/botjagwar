-- Migration 003: Add ranked full-text search for json_dictionary pages.
--
-- Apply manually while the materialized-view refresh job is paused. Building
-- this GIN index over a production-sized json_dictionary can take significant
-- time, disk space, and WAL capacity.

BEGIN;

CREATE INDEX json_dictionary_search_idx
    ON public.json_dictionary
    USING gin ((
        setweight(to_tsvector('simple'::regconfig, COALESCE(word::text, '')), 'A')
        || setweight(to_tsvector('simple'::regconfig, COALESCE(language::text, '')), 'B')
        || setweight(json_to_tsvector('simple'::regconfig, COALESCE(definitions, '[]'::json), '["string"]'::jsonb), 'C')
        || setweight(json_to_tsvector('simple'::regconfig, COALESCE(additional_data, '[]'::json), '["string"]'::jsonb), 'D')
    ));

CREATE OR REPLACE FUNCTION public.search_json_dictionary(
    p_query text,
    p_limit integer DEFAULT 21,
    p_offset bigint DEFAULT 0
)
RETURNS TABLE (
    word character varying(150),
    language character varying(10),
    part_of_speech character varying(15),
    definition_preview text,
    match_field text,
    rank double precision
)
LANGUAGE sql
STABLE
PARALLEL SAFE
SET search_path = pg_catalog, public
AS $function$
    WITH query AS (
        SELECT plainto_tsquery('simple'::regconfig, btrim(p_query)) AS value
    ), documents AS (
        SELECT
            dictionary.*,
            setweight(to_tsvector('simple'::regconfig, COALESCE(dictionary.word::text, '')), 'A') AS word_vector,
            setweight(to_tsvector('simple'::regconfig, COALESCE(dictionary.language::text, '')), 'B') AS language_vector,
            setweight(json_to_tsvector('simple'::regconfig, COALESCE(dictionary.definitions, '[]'::json), '["string"]'::jsonb), 'C') AS definitions_vector,
            setweight(json_to_tsvector('simple'::regconfig, COALESCE(dictionary.additional_data, '[]'::json), '["string"]'::jsonb), 'D') AS additional_data_vector
        FROM public.json_dictionary AS dictionary
    ), ranked AS (
        SELECT
            documents.word,
            documents.language,
            documents.part_of_speech,
            documents.definitions -> 0 ->> 'definition' AS definition_preview,
            CASE
                WHEN lower(documents.word::text) = lower(btrim(p_query)) THEN 'word'
                WHEN documents.word_vector @@ query.value THEN 'word'
                WHEN documents.language_vector @@ query.value THEN 'language'
                WHEN documents.definitions_vector @@ query.value THEN 'definitions'
                ELSE 'additional_data'
            END AS match_field,
            CASE
                WHEN lower(documents.word::text) = lower(btrim(p_query)) THEN 5.0
                WHEN documents.word_vector @@ query.value THEN 4.0
                WHEN documents.language_vector @@ query.value THEN 3.0
                WHEN documents.definitions_vector @@ query.value THEN 2.0
                ELSE 1.0
            END + 0.5 * ts_rank_cd(
                ARRAY[0.1, 0.2, 0.4, 1.0]::real[],
                documents.word_vector || documents.language_vector || documents.definitions_vector || documents.additional_data_vector,
                query.value,
                32
            )::double precision AS rank
        FROM documents
        CROSS JOIN query
        WHERE numnode(query.value) > 0
          AND (documents.word_vector || documents.language_vector || documents.definitions_vector || documents.additional_data_vector) @@ query.value
    ), pages AS (
        SELECT ranked.*, row_number() OVER (
            PARTITION BY lower(ranked.word::text)
            ORDER BY ranked.rank DESC, ranked.language, ranked.part_of_speech
        ) AS page_row
        FROM ranked
    )
    SELECT pages.word, pages.language, pages.part_of_speech, pages.definition_preview, pages.match_field, pages.rank
    FROM pages
    WHERE pages.page_row = 1
    ORDER BY pages.rank DESC, lower(pages.word::text) COLLATE "C", pages.word COLLATE "C"
    LIMIT least(greatest(COALESCE(p_limit, 21), 1), 101)
    OFFSET greatest(COALESCE(p_offset, 0), 0);
$function$;

REVOKE ALL ON FUNCTION public.search_json_dictionary(text, integer, bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.search_json_dictionary(text, integer, bigint) TO botjagwar;

ANALYZE public.json_dictionary;
NOTIFY pgrst, 'reload schema';

COMMIT;
