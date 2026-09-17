-- Migration 002: Add pgvector support for NLLB translation sentence embeddings
--
-- This migration:
--   1. Ensures the pgvector extension is enabled.
--   2. Adds a word2vec vector column (300 dimensions) to nllb_translations.
--   3. Creates an IVFFlat index for fast cosine-similarity lookups.
--
-- Prerequisites: PostgreSQL 11+ with the pgvector extension available.
-- Apply with: psql -U <user> -d <database> -f 002_add_pgvector_nllb_translations.sql

BEGIN;

-- Enable the pgvector extension if it is not already installed.
CREATE EXTENSION IF NOT EXISTS vector;

-- Add the vector column that will hold the word2vec embedding for each sentence.
-- Standard word2vec models (e.g. word2vec-google-news-300) produce 300-dimensional vectors.
ALTER TABLE public.nllb_translations
    ADD COLUMN IF NOT EXISTS sentence_vector vector(300);

-- Create an IVFFlat index for approximate nearest-neighbour search using cosine distance.
-- 'lists' is tuned for tables with up to ~1 M rows; increase for larger datasets.
CREATE INDEX IF NOT EXISTS nllb_translations_sentence_vector_cosine_idx
    ON public.nllb_translations
    USING ivfflat (sentence_vector vector_cosine_ops)
    WITH (lists = 100);

COMMIT;
