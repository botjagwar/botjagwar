#!/usr/bin/env python3
from __future__ import annotations

"""
populate_nllb_translation_vectors.py
=====================================
Computes a word2vec embedding for every row in the ``nllb_translations`` table
and stores the result in the ``sentence_vector`` (vector(300)) column.

The script uses Gensim's ``downloader`` API to fetch a pre-trained word2vec
model (``word2vec-google-news-300`` by default, which yields 300-dimensional
vectors that match the column definition).  For sentences that contain multiple
tokens the embedding is the *mean* of the individual token vectors; sentences
whose tokens are all out-of-vocabulary receive a zero vector.

Rows whose ``sentence_vector`` column is already populated are skipped by
default so the script is safe to re-run.

Usage
-----
    python scripts/populate_nllb_translation_vectors.py [options]

Options
-------
    --db-url    Full psycopg2-compatible connection URL.
                Defaults to BOTJAGWAR_CONFIG or /etc/botjagwar/config.ini
                (key ``database_uri`` in section ``[global]``).
    --model     Gensim downloader model name.
                Defaults to ``word2vec-google-news-300``.
    --batch     Number of rows to process per database transaction.
                Defaults to 500.
    --all       Re-compute vectors even for rows that already have one.
    --dry-run   Print statistics but do not write anything to the database.

Prerequisites
-------------
    pip install gensim psycopg2-binary pgvector
"""

import argparse
import configparser
import logging
import os
import sys
from typing import TYPE_CHECKING, Optional

import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector

if TYPE_CHECKING:
    import gensim

from api.utils.word2vec import VECTOR_DIM, get_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "word2vec-google-news-300"


def load_model(model_name: str) -> "gensim.models.KeyedVectors":
    """
    Return a Gensim KeyedVectors model, loading it only once per process.

    This delegates to the shared cache in :mod:`api.utils.word2vec` so the same
    model is not loaded repeatedly when this script is imported by other code.

    Args:
        model_name: A model name accepted by :func:`gensim.downloader.load`.

    Returns:
        A Gensim ``KeyedVectors`` (or compatible) object ready for lookup.
    """
    model = get_model(model_name)
    if model is None:
        raise RuntimeError(f"Could not load word2vec model '{model_name}'.")
    return model


def sentence_to_vector(text: str, model) -> Optional[np.ndarray]:
    """
    Convert a sentence string to a 300-dimensional word2vec vector.

    Tokenises by whitespace and lower-cases each token, then strips common
    punctuation characters before looking each token up in the model.  Returns
    the mean of all in-vocabulary token vectors.  If no token is found in the
    model vocabulary a zero vector is returned so the database column is never
    NULL.

    Args:
        text:  The sentence text to vectorise.
        model: A Gensim KeyedVectors (or equivalent) object.

    Returns:
        A numpy array of shape (300,) with dtype float32.
    """
    tokens = text.lower().split()
    vectors = []
    for token in tokens:
        clean = token.strip(".,;:!?\"'()[]{}—–-")
        if clean in model:
            vectors.append(model[clean])

    if vectors:
        return np.mean(vectors, axis=0).astype(np.float32)

    return np.zeros(VECTOR_DIM, dtype=np.float32)


def read_db_url_from_config() -> str:
    """
    Read the PostgreSQL connection URL from the botjagwar configuration file.

    Reads ``BOTJAGWAR_CONFIG`` or ``/etc/botjagwar/config.ini`` and returns
    the ``database_uri`` key in the ``[global]`` section.

    Raises:
        configparser.Error: If the file does not exist, cannot be parsed, or
            the expected section/key is absent.
    """
    config_path = os.environ.get("BOTJAGWAR_CONFIG", "/etc/botjagwar/config.ini")
    config = configparser.ConfigParser(interpolation=None)
    config.read(config_path)
    try:
        return config.get("global", "database_uri")
    except configparser.Error as exc:
        raise configparser.Error(
            f"Could not read 'database_uri' from [{config_path}]: {exc}"
        ) from exc


def populate_vectors(
    db_url: str,
    model_name: str = DEFAULT_MODEL_NAME,
    batch_size: int = 500,
    recompute_all: bool = False,
    dry_run: bool = False,
) -> None:
    """
    Main routine: iterate over all nllb_translations rows and write vectors.

    Args:
        db_url:         psycopg2-compatible connection URL.
        model_name:     Gensim downloader model identifier.
        batch_size:     Number of rows committed per transaction.
        recompute_all:  When True, also update rows that already have a vector.
        dry_run:        When True, skip the UPDATE statements.
    """
    model = load_model(model_name)

    dsn = db_url.replace("postgresql+psycopg2://", "postgresql://")

    log.info("Connecting to database …")
    conn = psycopg2.connect(dsn)
    register_vector(conn)
    conn.autocommit = False

    # Count target rows.
    count_filter = "" if recompute_all else "WHERE sentence_vector IS NULL"
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) FROM public.nllb_translations {count_filter};"
        )
        total = cur.fetchone()[0]
    log.info("Rows to process: %d", total)

    updated = 0
    skipped = 0
    offset = 0

    select_filter = "" if recompute_all else "WHERE sentence_vector IS NULL"
    while True:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT ctid, sentence FROM public.nllb_translations "
                f"{select_filter} "
                "ORDER BY ctid "
                "LIMIT %s OFFSET %s;",
                (batch_size, offset),
            )
            rows = cur.fetchall()

        if not rows:
            break

        batch_updates = []
        for row_ctid, sentence_text in rows:
            if not sentence_text:
                skipped += 1
                continue
            vec = sentence_to_vector(sentence_text, model)
            batch_updates.append((vec, row_ctid))
            updated += 1

        if batch_updates and not dry_run:
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE public.nllb_translations "
                    "SET sentence_vector = %s "
                    "WHERE ctid = %s;",
                    batch_updates,
                )
            conn.commit()
            log.info(
                "Progress: ~%d / %d (skipped %d empty sentences so far)",
                min(offset + batch_size, total),
                total,
                skipped,
            )
        elif batch_updates and dry_run:
            log.info(
                "[dry-run] Would update %d rows in this batch (offset %d).",
                len(batch_updates),
                offset,
            )

        offset += batch_size

    if not dry_run:
        log.info(
            "Done. Updated %d nllb_translations rows, skipped %d.", updated, skipped
        )
    else:
        log.info(
            "[dry-run] Would have updated %d rows, skipped %d.", updated, skipped
        )

    conn.close()


def main() -> None:
    """Parse command-line arguments and run the population script."""
    parser = argparse.ArgumentParser(
        description=(
            "Populate sentence_vector column in nllb_translations using "
            "word2vec embeddings."
        )
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help=(
            "PostgreSQL connection URL "
            "(e.g. postgresql://user:pass@host/dbname). "
            "Defaults to BOTJAGWAR_CONFIG or /etc/botjagwar/config.ini."
        ),
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_NAME,
        help=f"Gensim downloader model name (default: {DEFAULT_MODEL_NAME}).",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=500,
        help="Number of rows per database transaction (default: 500).",
    )
    parser.add_argument(
        "--all",
        dest="recompute_all",
        action="store_true",
        help="Re-compute vectors even for rows that already have one.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute vectors but do not write them to the database.",
    )
    args = parser.parse_args()

    db_url = args.db_url
    if db_url is None:
        try:
            db_url = read_db_url_from_config()
        except Exception as exc:
            log.error("Could not read database URL from config: %s", exc)
            log.error("Please pass --db-url explicitly.")
            sys.exit(1)

    populate_vectors(
        db_url=db_url,
        model_name=args.model,
        batch_size=args.batch,
        recompute_all=args.recompute_all,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
