--
-- PostgreSQL database dump
--

-- Dumped from database version 11.7 (Raspbian 11.7-0+deb10u1)
-- Dumped by pg_dump version 11.7 (Raspbian 11.7-0+deb10u1)

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

SET default_with_oids = false;

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
    definition character varying(250),
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

CREATE VIEW public.unaggregated_dictionary_with_undefined_words AS
 SELECT wrd.id AS word_id,
    wrd.word,
    wrd.language,
    wrd.part_of_speech,
    defn.id AS definition_id,
    defn.definition,
    defn.definition_language
   FROM ((public.dictionary dct
     LEFT outer JOIN public.word wrd ON ((wrd.id = dct.word)))
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
-- Name: curated_convergent_translations; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.curated_convergent_translations AS
 SELECT convergent_translations.word_id,
    convergent_translations.word,
    convergent_translations.language,
    convergent_translations.part_of_speech,
    convergent_translations.en_definition_id,
    convergent_translations.en_definition,
    convergent_translations.fr_definition_id,
    convergent_translations.fr_definition,
    convergent_translations.mg_definition_id,
    convergent_translations.suggested_definition
   FROM public.convergent_translations
  WHERE (NOT (concat(convergent_translations.word_id, '_', convergent_translations.mg_definition_id) IN ( SELECT concat(dictionary.word, '_', dictionary.definition) AS concat
           FROM public.dictionary)));


ALTER TABLE public.curated_convergent_translations OWNER TO postgres;

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
-- Name: es_mg; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.es_mg AS
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
          WHERE (((word.language)::text = 'es'::text) AND ((definitions.definition_language)::text = 'mg'::text))) t
  WHERE (t.definition IS NOT NULL)
  WITH NO DATA;


ALTER TABLE public.es_mg OWNER TO postgres;

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
-- Name: inconsistent_definitions; Type: VIEW; Schema: public; Owner: postgres
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


ALTER TABLE public.inconsistent_definitions OWNER TO postgres;

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
-- Name: m_curated_convergent_translation; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.m_curated_convergent_translation AS
 SELECT convergent_translations.word_id,
    convergent_translations.word,
    convergent_translations.language,
    convergent_translations.part_of_speech,
    convergent_translations.en_definition_id,
    convergent_translations.en_definition,
    convergent_translations.fr_definition_id,
    convergent_translations.fr_definition,
    convergent_translations.mg_definition_id,
    convergent_translations.suggested_definition
   FROM public.convergent_translations
  WHERE (NOT (EXISTS ( SELECT dictionary.word,
            dictionary.definition
           FROM public.dictionary
          WHERE ((dictionary.word = convergent_translations.word_id) AND (dictionary.definition = convergent_translations.mg_definition_id)))));


ALTER TABLE public.m_curated_convergent_translation OWNER TO postgres;

--
-- Name: matview_inconsistent_definitions; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.matview_inconsistent_definitions AS
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
  WHERE ((t1.w2 IS NOT NULL) AND ((t1.w2_pos)::text <> (t1.w1_pos)::text) AND ((((t1.w1_pos)::text = 'ana'::text) AND ((t1.w2_pos)::text = ANY (ARRAY[('mpam-ana'::character varying)::text, ('mat'::character varying)::text]))) OR (((t1.w1_pos)::text = ANY (ARRAY[('mat'::character varying)::text, ('mpam-ana'::character varying)::text])) AND ((t1.w2_pos)::text = 'ana'::text))))
  WITH NO DATA;


ALTER TABLE public.matview_inconsistent_definitions OWNER TO postgres;

--
-- Name: vw_new_associations; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.vw_new_associations AS
SELECT
    NULL::text AS type,
    NULL::bigint AS id,
    NULL::character varying(150) AS word,
    NULL::character varying(10) AS language,
    NULL::character varying(15) AS part_of_speech,
    NULL::timestamp with time zone AS associated_on,
    NULL::json AS definitions,
    NULL::json AS additional_data;


ALTER TABLE public.vw_new_associations OWNER TO postgres;

--
-- Name: matview_new_associations; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.matview_new_associations AS
 SELECT vw_new_associations.type,
    vw_new_associations.id,
    vw_new_associations.word,
    vw_new_associations.language,
    vw_new_associations.part_of_speech,
    vw_new_associations.associated_on,
    vw_new_associations.definitions,
    vw_new_associations.additional_data
   FROM public.vw_new_associations
  WITH NO DATA;


ALTER TABLE public.matview_new_associations OWNER TO postgres;

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
-- Name: new_associations_per_day; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.new_associations_per_day AS
 SELECT count(*) AS count,
    ((new_associations.associated_on)::timestamp without time zone)::date AS date
   FROM public.new_associations
  GROUP BY (((new_associations.associated_on)::timestamp without time zone)::date)
  ORDER BY (((new_associations.associated_on)::timestamp without time zone)::date) DESC;


ALTER TABLE public.new_associations_per_day OWNER TO postgres;

--
-- Name: pl_mg; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.pl_mg AS
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
          WHERE (((word.language)::text = 'pl'::text) AND ((definitions.definition_language)::text = 'mg'::text))) t
  WHERE (t.definition IS NOT NULL)
  WITH NO DATA;


ALTER TABLE public.pl_mg OWNER TO postgres;

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
-- Name: zh_mg; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.zh_mg AS
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
          WHERE (((word.language)::text = ANY (ARRAY['zho'::text, 'zh'::text, 'cmn'::text])) AND ((definitions.definition_language)::text = 'mg'::text))) t
  WHERE (t.definition IS NOT NULL)
  WITH NO DATA;


ALTER TABLE public.zh_mg OWNER TO postgres;

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
-- Name: idx_16427_date_changed; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16427_date_changed ON public.definitions USING btree (date_changed);


--
-- Name: idx_16427_definition; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16427_definition ON public.definitions USING gin (to_tsvector('simple'::regconfig, (definition)::text));


--
-- Name: idx_16427_definition_2; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16427_definition_2 ON public.definitions USING btree (definition);


--
-- Name: idx_16427_definition_language; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16427_definition_language ON public.definitions USING btree (definition_language);


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
-- Name: idx_16449_language; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16449_language ON public.word USING btree (language);


--
-- Name: idx_16449_part_of_speech; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16449_part_of_speech ON public.word USING btree (part_of_speech);


--
-- Name: idx_16449_word; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16449_word ON public.word USING btree (word);


--
-- Name: idx_16449_word_2; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16449_word_2 ON public.word USING gin (to_tsvector('simple'::regconfig, (word)::text));


--
-- Name: idx_16449_word_3; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_16449_word_3 ON public.word USING btree (word, language, part_of_speech);


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
-- Name: idx_en_mg_word_defn; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_en_mg_word_defn ON public.en_mg USING btree (word, definition);


--
-- Name: idx_en_mg_word_pos; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_en_mg_word_pos ON public.en_mg USING btree (word, part_of_speech);


--
-- Name: idx_fr_mg_word_defn; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_fr_mg_word_defn ON public.fr_mg USING btree (word, definition);


--
-- Name: idx_fr_mg_word_pos; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_fr_mg_word_pos ON public.fr_mg USING btree (word, part_of_speech);


--
-- Name: idx_json_dictionary_1; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_json_dictionary_1 ON public.json_dictionary USING btree (word, language, part_of_speech);


--
-- Name: idx_json_dictionary_2; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_json_dictionary_2 ON public.json_dictionary USING btree (last_modified);


--
-- Name: idx_json_dictionary_3; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_json_dictionary_3 ON public.json_dictionary USING btree (id);


--
-- Name: idx_mv_word_with_openmt_translation; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mv_word_with_openmt_translation ON public.mv_word_with_openmt_translation USING btree (lowercase_word, word_id);


--
-- Name: idx_new_associations_word_defn; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_new_associations_word_defn ON public.new_associations USING btree (word, definition);


--
-- Name: idx_new_associations_word_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_new_associations_word_status ON public.new_associations USING btree (word, status);


--
-- Name: idx_suggested_translations_en_mg_1; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_suggested_translations_en_mg_1 ON public.suggested_translations_en_mg USING btree (word, language, part_of_speech);


--
-- Name: idx_suggested_translations_en_mg_2; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_suggested_translations_en_mg_2 ON public.suggested_translations_en_mg USING btree (suggested_definition);


--
-- Name: idx_suggested_translations_en_mg_3; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_suggested_translations_en_mg_3 ON public.suggested_translations_en_mg USING btree (definition);


--
-- Name: idx_suggested_translations_en_mg_suggested_definition; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_suggested_translations_en_mg_suggested_definition ON public.suggested_translations_en_mg USING btree (suggested_definition);


--
-- Name: idx_suggested_translations_en_mg_suggested_language; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_suggested_translations_en_mg_suggested_language ON public.suggested_translations_en_mg USING btree (language);


--
-- Name: idx_suggested_translations_en_mg_word; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_suggested_translations_en_mg_word ON public.suggested_translations_en_mg USING btree (word);


--
-- Name: idx_suggested_translations_fr_mg_1; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_suggested_translations_fr_mg_1 ON public.suggested_translations_fr_mg USING btree (word, language, part_of_speech);


--
-- Name: idx_suggested_translations_fr_mg_2; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_suggested_translations_fr_mg_2 ON public.suggested_translations_fr_mg USING btree (suggested_definition);


--
-- Name: idx_suggested_translations_fr_mg_3; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_suggested_translations_fr_mg_3 ON public.suggested_translations_fr_mg USING btree (definition);


--
-- Name: unique_association; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX unique_association ON public.dictionary USING btree (word, definition);


--
-- Name: word_language_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX word_language_idx ON public.word USING btree (word, language);


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
-- Name: vw_new_associations _RETURN; Type: RULE; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.vw_new_associations AS
 SELECT 'Word'::text AS type,
    wrd.id,
    wrd.word,
    wrd.language,
    wrd.part_of_speech,
    max(dct.associated_on) AS associated_on,
    array_to_json(array_agg(json_build_object('type', 'Definition', 'id', defn.id, 'definition', defn.definition, 'language', defn.definition_language, 'associated_on', dct.associated_on, 'status', dct.status, 'definition_last_modified', defn.date_changed))) AS definitions,
    ( SELECT array_to_json(array_agg(json_build_object('type', 'AdditionalData', 'data_type', awi.type, 'data', awi.information))) AS array_to_json
           FROM public.additional_word_information awi
          WHERE (awi.word_id = wrd.id)
          GROUP BY awi.word_id) AS additional_data
   FROM ((public.new_associations dct
     LEFT JOIN public.word wrd ON ((wrd.id = dct.word)))
     JOIN public.definitions defn ON ((defn.id = dct.definition)))
  GROUP BY wrd.id;


--
-- Name: definitions on_definition_changed_add_pending_definition_change; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER on_definition_changed_add_pending_definition_change AFTER UPDATE ON public.definitions FOR EACH ROW EXECUTE PROCEDURE public.add_pending_definition_change();


--
-- Name: dictionary on_dictionary_added_add_new_association; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER on_dictionary_added_add_new_association AFTER INSERT ON public.dictionary FOR EACH ROW EXECUTE PROCEDURE public.add_new_association();


--
-- Name: dictionary on_row_deleted; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER on_row_deleted BEFORE DELETE ON public.dictionary FOR EACH ROW EXECUTE PROCEDURE public.events_rel_definition_word_deleted();


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
-- Name: new_associations new_association_definitions_ibfk_1; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.new_associations
    ADD CONSTRAINT new_association_definitions_ibfk_1 FOREIGN KEY (definition) REFERENCES public.definitions(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: new_associations new_association_ibfk_1; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.new_associations
    ADD CONSTRAINT new_association_ibfk_1 FOREIGN KEY (word) REFERENCES public.word(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--
