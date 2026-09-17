"""
api/utils/word2vec.py
=====================
Shared helpers for converting text to an embedding vector.

Two backends are supported, selected by the shape of ``model_name``:

* Gensim word2vec/GloVe models (e.g. ``word2vec-google-news-300``), loaded via
  ``gensim.downloader`` and combined into a sentence vector by averaging the
  in-vocabulary token vectors.
* Sentence-transformers models identified by a Hugging Face repository id
  containing a ``/`` (e.g. ``BAAI/bge-small-en``), which encode the whole text
  contextually and generally provide better semantic quality than a bag-of-
  words average.

Each model is loaded at most once per process (lazy singleton) so that
multiple callers inside the same service do not each pay the model-loading cost.
When the required library or the requested model is not available the helper
returns ``None`` gracefully, which allows callers to simply omit the vector
field.

Typical usage
-------------
    from api.utils.word2vec import text_to_vector

    vec = text_to_vector("a useful definition")
    if vec is not None:
        payload["sentence_vector"] = vec.tolist()
"""

import logging
import threading
from typing import TYPE_CHECKING, Any, Dict, Optional

import numpy as np

if TYPE_CHECKING:
    from gensim.models import KeyedVectors
    from sentence_transformers import SentenceTransformer

log = logging.getLogger(__name__)

# Default model; 300-dimensional vectors.
DEFAULT_MODEL_NAME = "word2vec-google-news-300"
VECTOR_DIM = 300

# Process-level cache keyed by model name.  Loading is expensive, so we keep one
# model in memory per name and reuse it across callers and threads.
_model_cache: Dict[str, "KeyedVectors"] = {}
_model_lock = threading.Lock()

# Separate cache for sentence-transformers models (distinct library/object type).
_sentence_transformer_cache: Dict[str, "SentenceTransformer"] = {}
_sentence_transformer_lock = threading.Lock()


def clear_model_cache() -> None:
    """Clear the process-level word2vec and sentence-transformer model caches.

    Intended for tests.
    """
    _model_cache.clear()
    _sentence_transformer_cache.clear()


def _is_sentence_transformer_model(model_name: str) -> bool:
    """Return whether ``model_name`` refers to a sentence-transformers model.

    Sentence-transformers/Hugging Face repository ids are namespaced as
    ``<owner>/<model>`` (e.g. ``BAAI/bge-small-en``), whereas Gensim downloader
    model names are single tokens (e.g. ``word2vec-google-news-300``).
    """
    return "/" in model_name


def get_sentence_transformer_model(model_name: str) -> Optional["SentenceTransformer"]:
    """
    Return the cached ``SentenceTransformer`` model, loading it on first call.

    Returns ``None`` if ``sentence-transformers`` is not installed or the model
    cannot be loaded.

    Args:
        model_name: A Hugging Face model id, e.g. ``BAAI/bge-small-en``.

    Returns:
        A ``SentenceTransformer`` instance, or ``None``.
    """
    cached = _sentence_transformer_cache.get(model_name)
    if cached is not None:
        return cached

    with _sentence_transformer_lock:
        # Double-checked locking: another thread may have loaded the model
        # while we were waiting for the lock.
        cached = _sentence_transformer_cache.get(model_name)
        if cached is not None:
            return cached

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore  # optional dep

            log.info("Loading sentence-transformers model '%s' …", model_name)
            model = SentenceTransformer(model_name)
            _sentence_transformer_cache[model_name] = model
            log.info("sentence-transformers model '%s' loaded.", model_name)
            return model
        except Exception as exc:
            log.warning("Could not load sentence-transformers model '%s': %s", model_name, exc)
            return None


def get_model(model_name: str = DEFAULT_MODEL_NAME) -> Optional["KeyedVectors"]:
    """
    Return the cached Gensim KeyedVectors model, loading it on first call.

    Returns ``None`` if Gensim is not installed or the model cannot be loaded.

    Args:
        model_name: A model name accepted by :func:`gensim.downloader.load`.

    Returns:
        A Gensim ``KeyedVectors`` object, or ``None``.
    """
    cached = _model_cache.get(model_name)
    if cached is not None:
        return cached

    with _model_lock:
        # Double-checked locking: another thread may have loaded the model
        # while we were waiting for the lock.
        cached = _model_cache.get(model_name)
        if cached is not None:
            return cached

        try:
            import gensim.downloader as gensim_api  # type: ignore  # optional dep

            log.info("Loading word2vec model '%s' …", model_name)
            model = gensim_api.load(model_name)
            _model_cache[model_name] = model
            log.info("word2vec model loaded (vocab size: %d).", len(model))
            return model  # type: ignore[no-any-return]
        except Exception as exc:
            log.warning("Could not load word2vec model '%s': %s", model_name, exc)
            return None


def text_to_vector(
    text: str,
    model_name: str = DEFAULT_MODEL_NAME,
) -> Optional[np.ndarray]:
    """
    Convert a text string to a sentence embedding.

    When ``model_name`` is a sentence-transformers repository id (containing a
    ``/``, e.g. ``BAAI/bge-small-en``), the whole text is encoded contextually
    by the transformer model. Otherwise ``model_name`` is treated as a Gensim
    downloader model: the text is tokenised by whitespace, lower-cased, and
    stripped of common punctuation before looking up each token, and the mean
    vector of all in-vocabulary tokens is returned. A zero vector is returned
    for fully out-of-vocabulary Gensim text so the column is never ``NULL``.

    Returns ``None`` when the required library or model cannot be loaded.

    Args:
        text:       The input text to vectorise.
        model_name: A Gensim downloader model name, or a sentence-transformers
                    Hugging Face repository id.

    Returns:
        A ``numpy`` array with dtype ``float32``, or ``None`` if the model is
        unavailable.
    """
    if _is_sentence_transformer_model(model_name):
        return _sentence_transformer_text_to_vector(text, model_name)

    model = get_model(model_name)
    if model is None:
        return None

    tokens = text.lower().split()
    vectors = []
    for token in tokens:
        clean = token.strip(".,;:!?\"'()[]{}—–-")
        if clean in model:
            vectors.append(model[clean])

    if vectors:
        return np.mean(vectors, axis=0).astype(np.float32)

    # Return a zero vector for fully OOV text so the column is never NULL.
    return np.zeros(VECTOR_DIM, dtype=np.float32)


def _sentence_transformer_text_to_vector(
    text: str,
    model_name: str,
) -> Optional[np.ndarray]:
    """
    Encode ``text`` with a cached sentence-transformers model.

    Args:
        text:       The input text to vectorise.
        model_name: A sentence-transformers Hugging Face repository id.

    Returns:
        A ``numpy`` array with dtype ``float32``, or ``None`` if the model is
        unavailable or encoding fails.
    """
    model = get_sentence_transformer_model(model_name)
    if model is None:
        return None

    try:
        embedding: Any = model.encode(text)
    except Exception as exc:
        log.warning("Could not encode text with sentence-transformers model '%s': %s", model_name, exc)
        return None

    return np.asarray(embedding, dtype=np.float32)
