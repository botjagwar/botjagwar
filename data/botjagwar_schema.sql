--
-- PostgreSQL database dump
--

-- Dumped from database version 14.12 (Ubuntu 14.12-0ubuntu0.22.04.1)
-- Dumped by pg_dump version 14.12 (Ubuntu 14.12-0ubuntu0.22.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: events_definition_changed_status; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.events_definition_changed_status AS ENUM (
    'PENDING',
    'PROCESSING',
    'DONE',
    'FAILED'
);


ALTER TYPE public.events_definition_changed_status OWNER TO postgres;

--
-- Name: add_new_association(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.add_new_association() RETURNS trigger
    LANGUAGE plpgsql
    AS $$BEGIN

insert into 
    new_associations (word, definition, associated_on, status)
values
    (NEW.word, NEW.definition, current_timestamp, 'PENDING');

RETURN NULL;
END$$;


ALTER FUNCTION public.add_new_association() OWNER TO postgres;

--
-- Name: add_pending_definition_change(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.add_pending_definition_change() RETURNS trigger
    LANGUAGE plpgsql
    AS $$BEGIN
IF NEW.definition != OLD.definition 
THEN
        INSERT into events_definition_changed (
            definition_id,   
            change_datetime,
            status,
            status_datetime,
            old_definition,
            new_definition,
            commentary
        ) values (
            NEW.id,
            current_timestamp,
            'PENDING',
            current_timestamp,
            OLD.definition,
            NEW.definition,
            ''
        );
END IF;
RETURN NULL;
END$$;


ALTER FUNCTION public.add_pending_definition_change() OWNER TO postgres;

--
-- Name: events_rel_definition_word_deleted(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.events_rel_definition_word_deleted() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        INSERT into events_rel_definition_word_deleted (
        definition,
        word,
        date_changed,
        comment
        ) values (
            OLD.definition,
            OLD.word,
            current_timestamp,
            'link removed'
        );
        RETURN OLD;

    END;
$$;


ALTER FUNCTION public.events_rel_definition_word_deleted() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: additional_word_information; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.additional_word_information (
    word_id bigint NOT NULL,
    type character varying(50) NOT NULL,
    information character varying(2000) NOT NULL
);


ALTER TABLE public.additional_word_information OWNER TO postgres;

--
-- Name: additional_word_information_by_type; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.additional_word_information_by_type AS
 SELECT additional_word_information.type,
    count(*) AS count
   FROM public.additional_word_information
  GROUP BY additional_word_information.type;


ALTER TABLE public.additional_word_information_by_type OWNER TO postgres;

--
-- Name: additional_word_information_types; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.additional_word_information_types AS
 SELECT DISTINCT additional_word_information.type
   FROM public.additional_word_information;


ALTER TABLE public.additional_word_information_types OWNER TO postgres;

--
-- Name: all_references; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.all_references AS
 SELECT DISTINCT additional_word_information.information
   FROM public.additional_word_information
  WHERE ((additional_word_information.type)::text = 'reference'::text);


ALTER TABLE public.all_references OWNER TO postgres;

--
-- Name: dictionary; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.dictionary (
    word bigint,
    definition bigint
);


ALTER TABLE public.dictionary OWNER TO postgres;

--
-- Name: concat_dictionary; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.concat_dictionary AS
 SELECT concat(dictionary.word, '_', dictionary.definition) AS concat
   FROM public.dictionary
  WITH NO DATA;


ALTER TABLE public.concat_dictionary OWNER TO postgres;

--
-- Name: definitions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.definitions (
    id bigint NOT NULL,
    date_changed timestamp with time zone,
    definition character varying(1000),
    definition_language character varying(6)
);


ALTER TABLE public.definitions OWNER TO postgres;

--
-- Name: word; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.word (
    id bigint NOT NULL,
    date_changed timestamp with time zone,
    word character varying(150),
    language character varying(10),
    part_of_speech character varying(15)
);


ALTER TABLE public.word OWNER TO postgres;

--
-- Name: en_mg; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.en_mg AS
 SELECT t.word,
    t.part_of_speech,
    t.definition
   FROM ( SELECT word.word,
            word.part_of_speech,
            ( SELECT ww.word
                   FROM public.word ww
                  WHERE (((ww.word)::text = (definitions.definition)::text) AND ((ww.part_of_speech)::text = (word.part_of_speech)::text) AND ((ww.language)::text = 'mg'::text))) AS definition
           FROM ((public.dictionary
             JOIN public.definitions ON ((definitions.id = dictionary.definition)))
             JOIN public.word ON ((dictionary.word = word.id)))
          WHERE (((word.language)::text = 'en'::text) AND ((definitions.definition_language)::text = 'mg'::text))) t
  WHERE (t.definition IS NOT NULL)
  WITH NO DATA;


ALTER TABLE public.en_mg OWNER TO postgres;

--
-- Name: fr_mg; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.fr_mg AS
 SELECT t.word,
    t.part_of_speech,
    t.definition
   FROM ( SELECT word.word,
            word.part_of_speech,
            ( SELECT ww.word
                   FROM public.word ww
                  WHERE (((ww.word)::text = (definitions.definition)::text) AND ((ww.part_of_speech)::text = (word.part_of_speech)::text) AND ((ww.language)::text = 'mg'::text))) AS definition
           FROM ((public.dictionary
             JOIN public.definitions ON ((definitions.id = dictionary.definition)))
             JOIN public.word ON ((dictionary.word = word.id)))
          WHERE (((word.language)::text = 'fr'::text) AND ((definitions.definition_language)::text = 'mg'::text))) t
  WHERE (t.definition IS NOT NULL)
  WITH NO DATA;


ALTER TABLE public.fr_mg OWNER TO postgres;

--
-- Name: unaggregated_dictionary; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.unaggregated_dictionary AS
 SELECT wrd.id AS word_id,
    wrd.word,
    wrd.language,
    wrd.part_of_speech,
    defn.id AS definition_id,
    defn.definition,
    defn.definition_language
   FROM ((public.dictionary dct
     LEFT JOIN public.word wrd ON ((wrd.id = dct.word)))
     JOIN public.definitions defn ON ((defn.id = dct.definition)));


ALTER TABLE public.unaggregated_dictionary OWNER TO postgres;

--
-- Name: suggested_translations_en_mg; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.suggested_translations_en_mg AS
 SELECT unaggregated_dictionary.word_id,
    unaggregated_dictionary.word,
    unaggregated_dictionary.language,
    unaggregated_dictionary.part_of_speech,
    unaggregated_dictionary.definition_id,
    unaggregated_dictionary.definition,
    unaggregated_dictionary.definition_language,
    en_mg.definition AS suggested_definition
   FROM (public.unaggregated_dictionary
     RIGHT JOIN public.en_mg ON ((((en_mg.word)::text = (unaggregated_dictionary.definition)::text) AND ((en_mg.part_of_speech)::text = (unaggregated_dictionary.part_of_speech)::text))))
  WHERE ((unaggregated_dictionary.definition_language)::text = 'en'::text)
  WITH NO DATA;


ALTER TABLE public.suggested_translations_en_mg OWNER TO postgres;

--
-- Name: suggested_translations_fr_mg; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.suggested_translations_fr_mg AS
 SELECT unaggregated_dictionary.word_id,
    unaggregated_dictionary.word,
    unaggregated_dictionary.language,
    unaggregated_dictionary.part_of_speech,
    unaggregated_dictionary.definition_id,
    unaggregated_dictionary.definition,
    unaggregated_dictionary.definition_language,
    fr_mg.definition AS suggested_definition
   FROM (public.unaggregated_dictionary
     RIGHT JOIN public.fr_mg ON ((((fr_mg.word)::text = (unaggregated_dictionary.definition)::text) AND ((fr_mg.part_of_speech)::text = (unaggregated_dictionary.part_of_speech)::text))))
  WHERE ((unaggregated_dictionary.definition_language)::text = 'fr'::text)
  WITH NO DATA;


ALTER TABLE public.suggested_translations_fr_mg OWNER TO postgres;

--
-- Name: convergent_translations; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.convergent_translations AS
 SELECT st_en.word_id,
    st_en.word,
    st_en.language,
    st_en.part_of_speech,
    st_en.definition_id AS en_definition_id,
    st_en.definition AS en_definition,
    st_fr.definition_id AS fr_definition_id,
    st_fr.definition AS fr_definition,
    ( SELECT min(definitions.id) AS min
           FROM public.definitions
          WHERE (((definitions.definition_language)::text = 'mg'::text) AND ((definitions.definition)::text = (st_en.suggested_definition)::text))) AS mg_definition_id,
    st_en.suggested_definition
   FROM (public.suggested_translations_fr_mg st_fr
     JOIN public.suggested_translations_en_mg st_en ON ((st_fr.word_id = st_en.word_id)))
  WHERE ((st_fr.suggested_definition)::text = (st_en.suggested_definition)::text);


ALTER TABLE public.convergent_translations OWNER TO postgres;

--
-- Name: db_stats; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.db_stats AS
 SELECT a.oid,
    a.table_schema,
    a.table_name,
    a.row_estimate,
    a.total_bytes,
    a.index_bytes,
    a.toast_bytes,
    a.table_bytes,
    pg_size_pretty(a.total_bytes) AS total,
    pg_size_pretty(a.index_bytes) AS index,
    pg_size_pretty(a.toast_bytes) AS toast,
    pg_size_pretty(a.table_bytes) AS "table"
   FROM ( SELECT a_1.oid,
            a_1.table_schema,
            a_1.table_name,
            a_1.row_estimate,
            a_1.total_bytes,
            a_1.index_bytes,
            a_1.toast_bytes,
            ((a_1.total_bytes - a_1.index_bytes) - COALESCE(a_1.toast_bytes, (0)::bigint)) AS table_bytes
           FROM ( SELECT c.oid,
                    n.nspname AS table_schema,
                    c.relname AS table_name,
                    c.reltuples AS row_estimate,
                    pg_total_relation_size((c.oid)::regclass) AS total_bytes,
                    pg_indexes_size((c.oid)::regclass) AS index_bytes,
                    pg_total_relation_size((c.reltoastrelid)::regclass) AS toast_bytes
                   FROM (pg_class c
                     LEFT JOIN pg_namespace n ON ((n.oid = c.relnamespace)))
                  WHERE (c.relkind = 'r'::"char")) a_1) a;


ALTER TABLE public.db_stats OWNER TO postgres;

--
-- Name: definitions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.definitions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.definitions_id_seq OWNER TO postgres;

--
-- Name: definitions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.definitions_id_seq OWNED BY public.definitions.id;


--
-- Name: events_definition_changed; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.events_definition_changed (
    id bigint NOT NULL,
    definition_id bigint NOT NULL,
    change_datetime timestamp with time zone NOT NULL,
    status public.events_definition_changed_status DEFAULT 'PENDING'::public.events_definition_changed_status NOT NULL,
    status_datetime timestamp with time zone NOT NULL,
    old_definition character varying(255) NOT NULL,
    new_definition character varying(255) NOT NULL,
    commentary text
);


ALTER TABLE public.events_definition_changed OWNER TO postgres;

--
-- Name: events_definition_changed_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.events_definition_changed_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.events_definition_changed_id_seq OWNER TO postgres;

--
-- Name: events_definition_changed_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.events_definition_changed_id_seq OWNED BY public.events_definition_changed.id;


--
-- Name: events_rel_definition_word_deleted; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.events_rel_definition_word_deleted (
    definition bigint NOT NULL,
    word bigint NOT NULL,
    date_changed date NOT NULL,
    comment text
);


ALTER TABLE public.events_rel_definition_word_deleted OWNER TO postgres;

--
-- Name: inconsistent_definitions; Type: VIEW; Schema: public; Owner: botjagwar
--

CREATE VIEW public.inconsistent_definitions AS
 SELECT t1.w_id,
    t1.w1,
    t1.w1_pos,
    t1.w1_lang,
    t1.w1_defn,
    t1.d_id,
    t1.d_lang,
    t1.w2,
    t1.w2_pos
   FROM ( SELECT w.id AS w_id,
            w.word AS w1,
            w.part_of_speech AS w1_pos,
            w.language AS w1_lang,
            d.definition AS w1_defn,
            d.id AS d_id,
            d.definition_language AS d_lang,
            ( SELECT w2.word
                   FROM public.word w2
                  WHERE (((w2.word)::text = (d.definition)::text) AND ((w2.language)::text = (d.definition_language)::text))
                 LIMIT 1) AS w2,
            ( SELECT w2.part_of_speech
                   FROM public.word w2
                  WHERE (((w2.word)::text = (d.definition)::text) AND ((w2.language)::text = (d.definition_language)::text))
                 LIMIT 1) AS w2_pos
           FROM ((public.dictionary x
             JOIN public.definitions d ON ((x.definition = d.id)))
             JOIN public.word w ON ((w.id = x.word)))) t1
  WHERE ((t1.w2 IS NOT NULL) AND ((t1.w2_pos)::text <> (t1.w1_pos)::text) AND ((((t1.w1_pos)::text = 'ana'::text) AND ((t1.w2_pos)::text = ANY (ARRAY[('mpam-ana'::character varying)::text, ('mat'::character varying)::text]))) OR (((t1.w1_pos)::text = ANY (ARRAY[('mat'::character varying)::text, ('mpam-ana'::character varying)::text])) AND ((t1.w2_pos)::text = 'ana'::text))));


ALTER TABLE public.inconsistent_definitions OWNER TO botjagwar;

--
-- Name: language; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.language (
    iso_code character varying(7) NOT NULL,
    english_name character varying(100),
    malagasy_name character varying(100),
    language_ancestor character varying(6)
);


ALTER TABLE public.language OWNER TO postgres;

--
-- Name: lemma_by_language; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.lemma_by_language AS
 SELECT word.language,
    count(*) AS lemmata
   FROM (public.additional_word_information
     JOIN public.word ON ((additional_word_information.word_id = word.id)))
  WHERE ((additional_word_information.type)::text = 'lemma'::text)
  GROUP BY word.language
  ORDER BY (count(*)) DESC
  WITH NO DATA;


ALTER TABLE public.lemma_by_language OWNER TO postgres;

--
-- Name: matview_suggested_translations_en_mg; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.matview_suggested_translations_en_mg AS
 SELECT dict.word AS word_id,
    ( SELECT ww.word
           FROM public.word ww
          WHERE (ww.id = dict.word)) AS word,
    ( SELECT ww.part_of_speech
           FROM public.word ww
          WHERE (ww.id = dict.word)) AS part_of_speech,
    ( SELECT ww.language
           FROM public.word ww
          WHERE (ww.id = dict.word)) AS language,
    ( SELECT dd.definition
           FROM public.definitions dd
          WHERE (dd.id = dict.definition)) AS definition,
    ( SELECT dd.definition_language
           FROM public.definitions dd
          WHERE (dd.id = dict.definition)) AS definition_language,
    ( SELECT json_agg(en_mg.definition) AS json_agg
           FROM public.en_mg
          WHERE (((en_mg.word)::text = (( SELECT dd.definition
                   FROM public.definitions dd
                  WHERE (dd.id = dict.definition)))::text) AND ((en_mg.part_of_speech)::text = (( SELECT ww.part_of_speech
                   FROM public.word ww
                  WHERE (ww.id = dict.word)))::text))) AS mg_definition
   FROM public.dictionary dict;


ALTER TABLE public.matview_suggested_translations_en_mg OWNER TO postgres;

--
-- Name: most_used_definitions; Type: VIEW; Schema: public; Owner: botjagwar
--

CREATE VIEW public.most_used_definitions AS
 SELECT dico.definition AS definition_id,
    count(*) AS words_using_definition,
    defn.definition,
    defn.definition_language
   FROM (public.dictionary dico
     JOIN public.definitions defn ON ((defn.id = dico.definition)))
  GROUP BY dico.definition, defn.definition, defn.definition_language
  ORDER BY (count(*)) DESC;


ALTER TABLE public.most_used_definitions OWNER TO botjagwar;

--
-- Name: mt_translated_definition; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mt_translated_definition (
    id bigint NOT NULL,
    date_changed timestamp with time zone,
    definition character varying(1000),
    definition_language character varying(6),
    method character varying(40)
);


ALTER TABLE public.mt_translated_definition OWNER TO postgres;

--
-- Name: word_with_openmt_translation; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.word_with_openmt_translation AS
 SELECT word.id,
    word.date_changed,
    word.word,
    word.language,
    word.part_of_speech,
    additional_word_information.word_id,
    additional_word_information.type,
    additional_word_information.information,
    lower((word.word)::text) AS lowercase_word
   FROM (public.word
     JOIN public.additional_word_information ON ((additional_word_information.word_id = word.id)))
  WHERE ((additional_word_information.type)::text = 'openmt_translation'::text);


ALTER TABLE public.word_with_openmt_translation OWNER TO postgres;

--
-- Name: mv_word_with_openmt_translation; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.mv_word_with_openmt_translation AS
 SELECT word_with_openmt_translation.id,
    word_with_openmt_translation.date_changed,
    word_with_openmt_translation.word,
    word_with_openmt_translation.language,
    word_with_openmt_translation.part_of_speech,
    word_with_openmt_translation.word_id,
    word_with_openmt_translation.type,
    word_with_openmt_translation.information,
    word_with_openmt_translation.lowercase_word
   FROM public.word_with_openmt_translation
  WITH NO DATA;


ALTER TABLE public.mv_word_with_openmt_translation OWNER TO postgres;

--
-- Name: new_associations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.new_associations (
    word bigint NOT NULL,
    definition bigint NOT NULL,
    associated_on timestamp with time zone,
    status public.events_definition_changed_status DEFAULT 'PENDING'::public.events_definition_changed_status NOT NULL
);


ALTER TABLE public.new_associations OWNER TO postgres;

--
-- Name: nllb_translations; Type: TABLE; Schema: public; Owner: botjagwar
--

CREATE TABLE public.nllb_translations (
    source_language character varying(40) NOT NULL,
    target_language character varying(40) NOT NULL,
    sentence character varying(2000),
    translation character varying(2000)
);


ALTER TABLE public.nllb_translations OWNER TO botjagwar;

--
-- Name: template_translations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.template_translations (
    source_template character varying(256),
    target_template character varying(256),
    source_language character varying(7),
    target_language character varying(7)
);


ALTER TABLE public.template_translations OWNER TO postgres;

--
-- Name: translation_method; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.translation_method (
    word bigint NOT NULL,
    definition bigint NOT NULL,
    translation_method character varying(40)
);


ALTER TABLE public.translation_method OWNER TO postgres;

--
-- Name: unaggregated_dictionary_with_undefined_words; Type: VIEW; Schema: public; Owner: botjagwar
--

CREATE VIEW public.unaggregated_dictionary_with_undefined_words AS
 SELECT wrd.id AS word_id,
    wrd.word,
    wrd.language,
    wrd.part_of_speech,
    defn.id AS definition_id,
    defn.definition,
    defn.definition_language
   FROM ((public.dictionary dct
     LEFT JOIN public.word wrd ON ((wrd.id = dct.word)))
     JOIN public.definitions defn ON ((defn.id = dct.definition)));


ALTER TABLE public.unaggregated_dictionary_with_undefined_words OWNER TO botjagwar;

--
-- Name: unaggregated_mt_translated_dictionary; Type: VIEW; Schema: public; Owner: botjagwar
--

CREATE VIEW public.unaggregated_mt_translated_dictionary AS
 SELECT w.id,
    w.date_changed,
    w.word,
    w.language,
    w.part_of_speech,
    mtd.id AS definition_id,
    mtd.definition,
    mtd.definition_language,
    mtd.method,
    ( SELECT definitions.definition
           FROM public.definitions
          WHERE (definitions.id = dictionary.definition)) AS source_definition,
    ( SELECT definitions.definition_language
           FROM public.definitions
          WHERE (definitions.id = dictionary.definition)) AS source_definition_language
   FROM ((public.dictionary dictionary
     JOIN public.word w ON ((w.id = dictionary.word)))
     JOIN public.mt_translated_definition mtd ON ((dictionary.definition = mtd.id)))
  GROUP BY w.id, w.date_changed, w.word, w.language, w.part_of_speech, mtd.id, mtd.definition, mtd.definition_language, mtd.method, ( SELECT definitions.definition
           FROM public.definitions
          WHERE (definitions.id = dictionary.definition)), ( SELECT definitions.definition_language
           FROM public.definitions
          WHERE (definitions.id = dictionary.definition));


ALTER TABLE public.unaggregated_mt_translated_dictionary OWNER TO botjagwar;

--
-- Name: unpublished_convergent_translations_mg; Type: VIEW; Schema: public; Owner: botjagwar
--

CREATE VIEW public.unpublished_convergent_translations_mg AS
 SELECT ct.word_id,
    ct.word,
    ct.language,
    ct.part_of_speech,
    ct.en_definition_id,
    ct.en_definition,
    ct.fr_definition_id,
    ct.fr_definition,
    ct.mg_definition_id,
    ct.suggested_definition
   FROM public.convergent_translations ct
  WHERE (NOT (((ct.mg_definition_id * 1000000000) + ct.word_id) IN ( SELECT ((dictionary.definition * 1000000000) + dictionary.word)
           FROM public.dictionary)));


ALTER TABLE public.unpublished_convergent_translations_mg OWNER TO botjagwar;

--
-- Name: untranslated_most_used_definitions; Type: VIEW; Schema: public; Owner: botjagwar
--

CREATE VIEW public.untranslated_most_used_definitions AS
 SELECT mud.definition_id,
    mud.words_using_definition,
    mud.definition,
    mud.definition_language,
    mtd.definition AS translated_definition
   FROM (public.most_used_definitions mud
     LEFT JOIN public.mt_translated_definition mtd ON ((mtd.id = mud.definition_id)))
  WHERE (mtd.definition IS NULL);


ALTER TABLE public.untranslated_most_used_definitions OWNER TO botjagwar;

--
-- Name: vw_en_mg; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.vw_en_mg AS
 SELECT t.word,
    t.part_of_speech,
    t.definition
   FROM ( SELECT word.word,
            word.part_of_speech,
            ( SELECT ww.word
                   FROM public.word ww
                  WHERE (((ww.word)::text = (definitions.definition)::text) AND ((ww.part_of_speech)::text = (word.part_of_speech)::text) AND ((ww.language)::text = 'mg'::text))) AS definition
           FROM ((public.dictionary
             JOIN public.definitions ON ((definitions.id = dictionary.definition)))
             JOIN public.word ON ((dictionary.word = word.id)))
          WHERE (((word.language)::text = 'en'::text) AND ((definitions.definition_language)::text = 'mg'::text))) t
  WHERE (t.definition IS NOT NULL);


ALTER TABLE public.vw_en_mg OWNER TO postgres;

--
-- Name: vw_fr_mg; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.vw_fr_mg AS
 SELECT t.word,
    t.part_of_speech,
    t.definition
   FROM ( SELECT word.word,
            word.part_of_speech,
            ( SELECT ww.word
                   FROM public.word ww
                  WHERE (((ww.word)::text = (definitions.definition)::text) AND ((ww.part_of_speech)::text = (word.part_of_speech)::text) AND ((ww.language)::text = 'mg'::text))) AS definition
           FROM ((public.dictionary
             JOIN public.definitions ON ((definitions.id = dictionary.definition)))
             JOIN public.word ON ((dictionary.word = word.id)))
          WHERE (((word.language)::text = 'fr'::text) AND ((definitions.definition_language)::text = 'mg'::text))) t
  WHERE (t.definition IS NOT NULL);


ALTER TABLE public.vw_fr_mg OWNER TO postgres;

--
-- Name: vw_json_dictionary; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.vw_json_dictionary AS
SELECT
    NULL::text AS type,
    NULL::bigint AS id,
    NULL::character varying(150) AS word,
    NULL::character varying(10) AS language,
    NULL::character varying(15) AS part_of_speech,
    NULL::timestamp with time zone AS last_modified,
    NULL::json AS definitions,
    NULL::json AS additional_data;


ALTER TABLE public.vw_json_dictionary OWNER TO postgres;

--
-- Name: word_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.word_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.word_id_seq OWNER TO postgres;

--
-- Name: word_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.word_id_seq OWNED BY public.word.id;


--
-- Name: word_with_additional_data; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.word_with_additional_data AS
SELECT
    NULL::text AS type,
    NULL::bigint AS id,
    NULL::character varying(150) AS word,
    NULL::character varying(10) AS language,
    NULL::character varying(15) AS part_of_speech,
    NULL::timestamp with time zone AS last_modified,
    NULL::json AS additional_data;


ALTER TABLE public.word_with_additional_data OWNER TO postgres;

--
-- Name: definitions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.definitions ALTER COLUMN id SET DEFAULT nextval('public.definitions_id_seq'::regclass);


--
-- Name: events_definition_changed id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.events_definition_changed ALTER COLUMN id SET DEFAULT nextval('public.events_definition_changed_id_seq'::regclass);


--
-- Name: word id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.word ALTER COLUMN id SET DEFAULT nextval('public.word_id_seq'::regclass);


--
-- Name: word idx_16449_primary; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.word
    ADD CONSTRAINT idx_16449_primary PRIMARY KEY (id);


--
-- Name: json_dictionary; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.json_dictionary AS
 SELECT 'Word'::text AS type,
    wrd.id,
    wrd.word,
    wrd.language,
    wrd.part_of_speech,
    wrd.date_changed AS last_modified,
    array_to_json(array_agg(json_build_object('type', 'Definition', 'id', defn.id, 'definition', defn.definition, 'language', defn.definition_language, 'last_modified', defn.date_changed))) AS definitions,
    ( SELECT array_to_json(array_agg(json_build_object('type', 'AdditionalData', 'data_type', awi.type, 'data', awi.information))) AS array_to_json
           FROM public.additional_word_information awi
          WHERE (awi.word_id = wrd.id)
          GROUP BY awi.word_id) AS additional_data
   FROM ((public.dictionary dct
     LEFT JOIN public.word wrd ON ((wrd.id = dct.word)))
     JOIN public.definitions defn ON ((defn.id = dct.definition)))
  GROUP BY wrd.id
  WITH NO DATA;


ALTER TABLE public.json_dictionary OWNER TO postgres;

--
-- Name: additional_word_information additional_data_row_is_unique; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.additional_word_information
    ADD CONSTRAINT additional_data_row_is_unique UNIQUE (word_id, type, information);


--
-- Name: definitions idx_16427_primary; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.definitions
    ADD CONSTRAINT idx_16427_primary PRIMARY KEY (id);


--
-- Name: events_definition_changed idx_16436_primary; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.events_definition_changed
    ADD CONSTRAINT idx_16436_primary PRIMARY KEY (id);


--
-- Name: language idx_16444_primary; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.language
    ADD CONSTRAINT idx_16444_primary PRIMARY KEY (iso_code);


--
-- Name: template_translations template_translations_source_template_source_language_targe_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.template_translations
    ADD CONSTRAINT template_translations_source_template_source_language_targe_key UNIQUE (source_template, source_language, target_template, target_language);


--
-- Name: translation_method translation_method_word_definition_translation_method_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.translation_method
    ADD CONSTRAINT translation_method_word_definition_translation_method_key UNIQUE (word, definition, translation_method);


--
-- Name: word word_is_unique; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.word
    ADD CONSTRAINT word_is_unique UNIQUE (word, part_of_speech, language);


--
-- Name: en_mg_line_is_unique; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX en_mg_line_is_unique ON public.en_mg USING btree (definition, part_of_speech, word);


--
-- Name: idx_16431_definition_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16431_definition_idx ON public.dictionary USING btree (definition);


--
-- Name: idx_16431_word_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16431_word_idx ON public.dictionary USING btree (word);


--
-- Name: idx_16436_definition_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16436_definition_id ON public.events_definition_changed USING btree (definition_id, old_definition, new_definition);


--
-- Name: idx_16436_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16436_status ON public.events_definition_changed USING btree (status);


--
-- Name: idx_16449_date_changed; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16449_date_changed ON public.word USING btree (date_changed);


--
-- Name: idx_16449_word_2; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16449_word_2 ON public.word USING gin (to_tsvector('simple'::regconfig, (word)::text));


--
-- Name: idx_additional_word_information_information; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_additional_word_information_information ON public.additional_word_information USING btree (information);


--
-- Name: idx_additional_word_information_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_additional_word_information_type ON public.additional_word_information USING btree (type);


--
-- Name: idx_additional_word_information_word_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_additional_word_information_word_id ON public.additional_word_information USING btree (word_id);


--
-- Name: idx_additional_word_information_word_id_info; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_additional_word_information_word_id_info ON public.additional_word_information USING btree (word_id, information);


--
-- Name: idx_concat_dictionary; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_concat_dictionary ON public.concat_dictionary USING btree (concat);


--
-- Name: idx_defn_defn_lang_matches; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_defn_defn_lang_matches ON public.definitions USING btree (definition, definition_language);


--
-- Name: idx_mtd_defn; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mtd_defn ON public.mt_translated_definition USING btree (id);


--
-- Name: idx_mtd_defn_2; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mtd_defn_2 ON public.mt_translated_definition USING btree (definition);


--
-- Name: idx_mv_word_with_openmt_translation; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mv_word_with_openmt_translation ON public.mv_word_with_openmt_translation USING btree (lowercase_word, word_id);


--
-- Name: idx_new_association_word; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_new_association_word ON public.new_associations USING btree (word);


--
-- Name: idx_word_language_pos; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_word_language_pos ON public.word USING btree (word, language, part_of_speech);


--
-- Name: idx_word_word; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_word_word ON public.word USING hash (word);


--
-- Name: line_is_unique; Type: INDEX; Schema: public; Owner: botjagwar
--

CREATE UNIQUE INDEX line_is_unique ON public.nllb_translations USING btree (source_language, target_language, sentence);


--
-- Name: suggested_translations_en_fr_line_is_unique; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX suggested_translations_en_fr_line_is_unique ON public.suggested_translations_fr_mg USING btree (word_id, definition_id, suggested_definition);


--
-- Name: suggested_translations_en_mg_line_is_unique; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX suggested_translations_en_mg_line_is_unique ON public.suggested_translations_en_mg USING btree (word_id, definition_id, suggested_definition);


--
-- Name: unique_association; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX unique_association ON public.dictionary USING btree (word, definition);


--
-- Name: word_language_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX word_language_idx ON public.word USING btree (word, language);


--
-- Name: word_language_part_of_speech_are_unique; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX word_language_part_of_speech_are_unique ON public.json_dictionary USING btree (word varchar_ops, language varchar_ops, part_of_speech varchar_ops) INCLUDE (word, language, part_of_speech);


--
-- Name: vw_json_dictionary _RETURN; Type: RULE; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.vw_json_dictionary AS
 SELECT 'Word'::text AS type,
    wrd.id,
    wrd.word,
    wrd.language,
    wrd.part_of_speech,
    wrd.date_changed AS last_modified,
    array_to_json(array_agg(json_build_object('type', 'Definition', 'id', defn.id, 'definition', defn.definition, 'language', defn.definition_language, 'last_modified', defn.date_changed))) AS definitions,
    ( SELECT array_to_json(array_agg(json_build_object('type', 'AdditionalData', 'data_type', awi.type, 'data', awi.information))) AS array_to_json
           FROM public.additional_word_information awi
          WHERE (awi.word_id = wrd.id)
          GROUP BY awi.word_id) AS additional_data
   FROM ((public.dictionary dct
     LEFT JOIN public.word wrd ON ((wrd.id = dct.word)))
     JOIN public.definitions defn ON ((defn.id = dct.definition)))
  GROUP BY wrd.id;


--
-- Name: word_with_additional_data _RETURN; Type: RULE; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.word_with_additional_data AS
 SELECT 'Word'::text AS type,
    wrd.id,
    wrd.word,
    wrd.language,
    wrd.part_of_speech,
    wrd.date_changed AS last_modified,
    array_to_json(array_agg(json_build_object('type', 'AdditionalData', 'data_type', awi.type, 'data', awi.information))) AS additional_data
   FROM (public.word wrd
     JOIN public.additional_word_information awi ON ((awi.word_id = wrd.id)))
  GROUP BY wrd.id;


--
-- Name: dictionary on_dictionary_added_add_new_association; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER on_dictionary_added_add_new_association AFTER INSERT ON public.dictionary FOR EACH ROW EXECUTE FUNCTION public.add_new_association();


--
-- Name: dictionary on_row_deleted; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER on_row_deleted BEFORE DELETE ON public.dictionary FOR EACH ROW EXECUTE FUNCTION public.events_rel_definition_word_deleted();


--
-- Name: dictionary dictionary_ibfk_1; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dictionary
    ADD CONSTRAINT dictionary_ibfk_1 FOREIGN KEY (word) REFERENCES public.word(id) ON UPDATE RESTRICT ON DELETE RESTRICT;


--
-- Name: dictionary dictionary_ibfk_2; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dictionary
    ADD CONSTRAINT dictionary_ibfk_2 FOREIGN KEY (definition) REFERENCES public.definitions(id) ON UPDATE RESTRICT ON DELETE RESTRICT;


--
-- Name: mt_translated_definition is_referenced_in_definition_table; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mt_translated_definition
    ADD CONSTRAINT is_referenced_in_definition_table FOREIGN KEY (id) REFERENCES public.definitions(id) NOT VALID;


--
-- PostgreSQL database dump complete
--

