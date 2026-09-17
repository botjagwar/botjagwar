import argparse
import logging
import os
import re
import threading
from typing import Any, List, Optional

import ctranslate2
import numpy as np
import sentencepiece as spm
from flask import Flask, jsonify, request
from gevent.pywsgi import WSGIServer

from api.utils.word2vec import text_to_vector
from api.utils.translation_quality import get_roundtrip_validation_error


DEFAULT_MODEL_PATH = "/opt/ctranslate/nllb-200-3.3B-int8"
DEFAULT_SP_MODEL_PATH = (
    "/opt/ctranslate/nllb-200-3.3B-int8/flores200_sacrebleu_tokenizer_spm.model"
)
DEFAULT_MAX_TEXT_LENGTH = 10_000
DEFAULT_MAX_CONSECUTIVE_REPEATED_TERMS = 3
DEFAULT_ROUNDTRIP_SOURCE_LANGUAGE = "eng_Latn"
DEFAULT_ROUNDTRIP_SIMILARITY_THRESHOLD = 0.60
# BGE is a sentence-transformers model chosen for contextual semantic comparison.
DEFAULT_EMBEDDING_MODEL_NAME = "BAAI/bge-small-en"

logger = logging.getLogger(__name__)
app = Flask(__name__)


class TranslationQualityError(RuntimeError):
    """Raised when a completed translation fails quality validation."""


class TranslationRequestError(ValueError):
    """Raised when an HTTP translation request is invalid."""


class CustomTranslator:
    """Translate text with a CTranslate2 NLLB model and SentencePiece tokenizer."""

    def __init__(
        self,
        ct_model_path: str,
        sp_model_path: str,
        device: str = "cuda",
        max_consecutive_repeated_terms: int = DEFAULT_MAX_CONSECUTIVE_REPEATED_TERMS,
        roundtrip_validation_enabled: bool = True,
        roundtrip_source_language: str = DEFAULT_ROUNDTRIP_SOURCE_LANGUAGE,
        roundtrip_similarity_threshold: float = DEFAULT_ROUNDTRIP_SIMILARITY_THRESHOLD,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL_NAME,
    ) -> None:
        """Initialize model paths, execution device, and quality configuration."""
        self._device = device
        self._ct_model_path = ct_model_path
        self._sp_model_path = sp_model_path
        self._translator: Optional[ctranslate2.Translator] = None
        self._inference_lock = threading.Lock()
        self._max_consecutive_repeated_terms = max_consecutive_repeated_terms
        self._roundtrip_validation_enabled = roundtrip_validation_enabled
        self._roundtrip_source_language = roundtrip_source_language
        self._roundtrip_similarity_threshold = roundtrip_similarity_threshold
        self._embedding_model_name = embedding_model_name
        self.sp = spm.SentencePieceProcessor()
        self.sp.load(self._sp_model_path)
        logger.info("SentencePiece model loaded from %s", self._sp_model_path)

    @property
    def translator(self) -> ctranslate2.Translator:
        """Return the lazily loaded CTranslate2 translator."""
        if self._translator is None:
            logger.info(
                "Loading CTranslate2 model from %s on %s",
                self._ct_model_path,
                self._device,
            )
            self._translator = ctranslate2.Translator(
                self._ct_model_path,
                device=self._device,
            )
        return self._translator

    def translate(
        self,
        source_sents: List[str],
        src_lang: str,
        tgt_lang: str,
        beam_size: int = 4,
        max_batch_size: int = 32,
        roundtrip_validation_enabled: Optional[bool] = None,
    ) -> List[str]:
        """Translate source sentences and validate each translated output."""
        translations = self._translate_without_quality_checks(
            source_sents,
            src_lang,
            tgt_lang,
            beam_size=beam_size,
            max_batch_size=max_batch_size,
        )
        for original_text, translated_text in zip(source_sents, translations):
            self._validate_translation_quality(
                original_text,
                translated_text,
                src_lang,
                tgt_lang,
                beam_size=beam_size,
                max_batch_size=max_batch_size,
                roundtrip_validation_enabled=roundtrip_validation_enabled,
            )
        return translations

    def _translate_without_quality_checks(
        self,
        source_sents: List[str],
        src_lang: str,
        tgt_lang: str,
        beam_size: int = 4,
        max_batch_size: int = 32,
    ) -> List[str]:
        """Translate source sentences without recursive quality checks."""
        if not source_sents:
            raise TranslationRequestError("At least one sentence is required.")

        stripped_sents = [sent.strip() for sent in source_sents]
        if any(not sent for sent in stripped_sents):
            raise TranslationRequestError("Text must not be empty.")

        source_sents_subworded = [
            [src_lang, *self.sp.encode_as_pieces(sent), "</s>"]
            for sent in stripped_sents
        ]
        target_prefix = [[tgt_lang] for _ in source_sents_subworded]

        # CTranslate2 translators are not thread-safe: concurrent greenlet
        # requests would interleave and mix up the hypotheses of different
        # requests, so translations are serialised with a lock.
        with self._inference_lock:
            logger.debug(
                "First subworded source sentence: %s", source_sents_subworded[0]
            )
            translations_subworded = self.translator.translate_batch(
                source_sents_subworded,
                batch_type="tokens",
                max_batch_size=max_batch_size,
                beam_size=beam_size,
                target_prefix=target_prefix,
            )

        hypotheses = [translation.hypotheses[0] for translation in translations_subworded]
        hypotheses = [
            hypothesis[1:] if hypothesis and hypothesis[0] == tgt_lang else hypothesis
            for hypothesis in hypotheses
        ]
        return [self.sp.decode(hypothesis) for hypothesis in hypotheses]

    def _validate_translation_quality(
        self,
        original_text: str,
        translated_text: str,
        source: str,
        target: str,
        beam_size: int,
        max_batch_size: int,
        roundtrip_validation_enabled: Optional[bool] = None,
    ) -> None:
        """Raise an error when translated text fails quality checks."""
        repeated_term = find_repeated_term(
            translated_text,
            self._max_consecutive_repeated_terms,
        )
        if repeated_term is not None:
            raise TranslationQualityError(
                "unsuccessful translation: translated output repeats the term "
                f"'{repeated_term}' more than "
                f"{self._max_consecutive_repeated_terms} consecutive times."
            )

        if not self._should_run_roundtrip_validation(
            source,
            target,
            roundtrip_validation_enabled,
        ):
            return

        roundtrip_text = self._translate_without_quality_checks(
            [translated_text],
            target,
            source,
            beam_size=beam_size,
            max_batch_size=max_batch_size,
        )[0]
        similarity = cosine_similarity_for_texts(
            original_text,
            roundtrip_text,
            self._embedding_model_name,
        )
        if similarity is None:
            raise TranslationQualityError(
                "unsuccessful translation: round-trip cosine similarity could not be "
                "computed because the embedding vectors were unavailable or had zero "
                f"norm. Parameters: source={source}, target={target}, "
                f"roundtrip_source={self._roundtrip_source_language}, "
                f"threshold={self._roundtrip_similarity_threshold:.3f}, "
                f"embedding_model={self._embedding_model_name}."
            )
        validation_error = get_roundtrip_validation_error(
            original_text,
            roundtrip_text,
            similarity,
            semantic_threshold=self._roundtrip_similarity_threshold,
        )
        if validation_error is not None:
            raise TranslationQualityError(
                "unsuccessful translation: round-trip validation failed because "
                f"{validation_error}. Parameters: "
                f"source={source}, target={target}, "
                f"roundtrip_source={self._roundtrip_source_language}, "
                f"embedding_model={self._embedding_model_name}, "
                f"original_text={original_text!r}, roundtrip_text={roundtrip_text!r}."
            )

    def _should_run_roundtrip_validation(
        self,
        source: str,
        target: str,
        enabled_override: Optional[bool] = None,
    ) -> bool:
        """Return whether the request should use English round-trip validation."""
        enabled = (
            self._roundtrip_validation_enabled
            if enabled_override is None
            else enabled_override
        )
        return (
            enabled
            and source == self._roundtrip_source_language
            and target != source
        )


def find_repeated_term(text: str, max_consecutive_count: int) -> Optional[str]:
    """Return a term repeated more than the allowed consecutive count."""
    if max_consecutive_count < 1:
        return None

    previous_term = None
    consecutive_count = 0
    for term in re.findall(r"\b[\w'-]+\b", text.lower()):
        if term == previous_term:
            consecutive_count += 1
        else:
            previous_term = term
            consecutive_count = 1
        if consecutive_count > max_consecutive_count:
            return term
    return None


def cosine_similarity_for_texts(
    first_text: str,
    second_text: str,
    embedding_model_name: str,
) -> Optional[float]:
    """Return cosine similarity for two text embedding vectors."""
    first_vector = text_to_vector(first_text, model_name=embedding_model_name)
    second_vector = text_to_vector(second_text, model_name=embedding_model_name)
    if first_vector is None or second_vector is None:
        return None

    first_norm = float(np.linalg.norm(first_vector))
    second_norm = float(np.linalg.norm(second_vector))
    if first_norm == 0.0 or second_norm == 0.0:
        return None

    return float(np.dot(first_vector, second_vector) / (first_norm * second_norm))


def get_env_bool(name: str, default: bool) -> bool:
    """Return a boolean environment variable value or a default."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_env_float(name: str, default: float) -> float:
    """Return a float environment variable value or a default."""
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be a float.") from error


def get_env_int(name: str, default: int) -> int:
    """Return an integer environment variable value or a default."""
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer.") from error


def get_request_text() -> str:
    """Extract and validate translation text from query params, form data, or JSON."""
    text = request.args.get("text")
    if text is None and request.is_json:
        payload = request.get_json(silent=True) or {}
        text = payload.get("text")
    if text is None:
        text = request.form.get("text")
    if not isinstance(text, str) or not text.strip():
        raise TranslationRequestError("Missing required text.")

    max_length = get_env_int("CTRANSLATE_MAX_TEXT_LENGTH", DEFAULT_MAX_TEXT_LENGTH)
    if len(text) > max_length:
        raise TranslationRequestError(
            f"Text too long. Maximum length is {max_length} characters."
        )
    return text.strip()


def get_roundtrip_validation_override() -> Optional[bool]:
    """Return the optional per-request round-trip validation setting."""
    value = request.args.get("roundtrip_validation")
    if value is None:
        return None
    if value.casefold() == "true":
        return True
    if value.casefold() == "false":
        return False
    raise TranslationRequestError("roundtrip_validation must be true or false.")


def create_translator() -> CustomTranslator:
    """Create a translator instance from environment configuration."""
    return CustomTranslator(
        os.environ.get("CTRANSLATE_MODEL_PATH", DEFAULT_MODEL_PATH),
        os.environ.get("CTRANSLATE_SP_MODEL_PATH", DEFAULT_SP_MODEL_PATH),
        device=os.environ.get("CTRANSLATE_DEVICE", "cuda"),
        max_consecutive_repeated_terms=get_env_int(
            "CTRANSLATE_MAX_CONSECUTIVE_REPEATED_TERMS",
            DEFAULT_MAX_CONSECUTIVE_REPEATED_TERMS,
        ),
        roundtrip_validation_enabled=get_env_bool(
            "CTRANSLATE_ROUNDTRIP_VALIDATION",
            True,
        ),
        roundtrip_source_language=os.environ.get(
            "CTRANSLATE_ROUNDTRIP_SOURCE_LANGUAGE",
            DEFAULT_ROUNDTRIP_SOURCE_LANGUAGE,
        ),
        roundtrip_similarity_threshold=get_env_float(
            "CTRANSLATE_ROUNDTRIP_SIMILARITY_THRESHOLD",
            DEFAULT_ROUNDTRIP_SIMILARITY_THRESHOLD,
        ),
        embedding_model_name=os.environ.get(
            "CTRANSLATE_EMBEDDING_MODEL",
            DEFAULT_EMBEDDING_MODEL_NAME,
        ),
    )


translator = create_translator()


@app.route("/health", methods=["GET"])
def health() -> Any:
    """Return a lightweight health response."""
    return jsonify({"status": "ok"})


@app.route("/translate/<source>/<target>", methods=["POST", "GET"])
def translate(source: str, target: str) -> Any:
    """Translate the request text from the source language to the target language."""
    try:
        text = get_request_text()
        translated_text = translator.translate(
            [text],
            source,
            target,
            roundtrip_validation_enabled=get_roundtrip_validation_override(),
        )[0]
        return jsonify({"translated": translated_text})
    except TranslationRequestError as error:
        return jsonify({"error": str(error)}), 400
    except TranslationQualityError as error:
        logger.warning("Translation quality validation failed: %s", error)
        return jsonify({"error": str(error)}), 502
    except RuntimeError as error:
        logger.exception("Translation failed")
        return jsonify({"error": str(error)}), 500


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the HTTP server."""
    parser = argparse.ArgumentParser(description="Run the CTranslate2 translation API.")
    parser.add_argument(
        "port",
        nargs="?",
        type=int,
        default=get_env_int("CTRANSLATE_PORT", 8888),
        help="Port to bind the HTTP server to.",
    )
    return parser.parse_args()


def main() -> None:
    """Start the translation API server."""
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    args = parse_args()
    http_server = WSGIServer(("127.0.0.1", args.port), app)
    logger.info("Serving CTranslate2 translation API on port %s", args.port)
    http_server.serve_forever()


if __name__ == "__main__":
    main()
