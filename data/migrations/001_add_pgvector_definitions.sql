-- Migration 001: Add pgvector support for definition embeddings
--
-- This migration:
--   1. Enables the pgvector extension.
--   2. Adds a word2vec vector column (300 dimensions) to the definitions table.
--   3. Creates an IVFFlat index for fast cosine-similarity lookups.
--
-- Prerequisites: PostgreSQL 11+ with the pgvector extension available.
-- Apply with: psql -U <user> -d <database> -f 001_add_pgvector_definitions.sql

BEGIN;

-- Enable the pgvector extension if it is not already installed.
CREATE EXTENSION IF NOT EXISTS vector;

-- Add the vector column that will hold the word2vec embedding for each definition.
-- Standard word2vec models produce 300-dimensional vectors.
ALTER TABLE public.definitions
    ADD COLUMN IF NOT EXISTS definition_vector vector(300);

-- Create an IVFFlat index for approximate nearest-neighbour search using cosine distance.
-- 'lists' is tuned for tables with up to ~1 M rows; increase for larger datasets.
CREATE INDEX IF NOT EXISTS definitions_vector_cosine_idx
    ON public.definitions
    USING ivfflat (definition_vector vector_cosine_ops)
    WITH (lists = 100);

COMMIT;
