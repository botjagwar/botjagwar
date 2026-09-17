import argparse
import logging
import os
import re
from typing import Any, Optional

import numpy as np
from flask import Flask, jsonify, request
from gevent.pywsgi import WSGIServer
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from transformers.modeling_utils import PreTrainedModel
from transformers.tokenization_utils_base import BatchEncoding, PreTrainedTokenizerBase

from api.utils.word2vec import text_to_vector
from api.utils.translation_quality import get_roundtrip_validation_error


DEFAULT_MODEL_ROOT = "/opt/ctranslate"
DEFAULT_MODEL_NAME = "nllb-200-3.3B"
DEFAULT_MAX_INPUT_TOKENS = 512
DEFAULT_MAX_GENERATED_TOKENS = 1000
DEFAULT_MAX_TEXT_LENGTH = 10_000
DEFAULT_MAX_CONSECUTIVE_REPEATED_TERMS = 3
DEFAULT_ROUNDTRIP_SOURCE_LANGUAGE = "eng_Latn"
DEFAULT_ROUNDTRIP_SIMILARITY_THRESHOLD = 0.60
# BGE is a sentence-transformers model chosen for contextual semantic comparison.
DEFAULT_EMBEDDING_MODEL_NAME = "BAAI/bge-small-en"

logger = logging.getLogger(__name__)
app = Flask(__name__)


class TranslatorError(Exception):
    """Raised when a translation cannot be completed."""


class TranslationQualityError(RuntimeError):
    """Raised when a completed translation fails quality validation."""


class TranslationRequestError(ValueError):
    """Raised when an HTTP translation request is invalid."""


class Translator:
    """Translate text with a Hugging Face sequence-to-sequence model."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        model_root: str = DEFAULT_MODEL_ROOT,
        device: str = "cpu",
        max_input_tokens: int = DEFAULT_MAX_INPUT_TOKENS,
        max_generated_tokens: int = DEFAULT_MAX_GENERATED_TOKENS,
        max_consecutive_repeated_terms: int = DEFAULT_MAX_CONSECUTIVE_REPEATED_TERMS,
        roundtrip_validation_enabled: bool = True,
        roundtrip_source_language: str = DEFAULT_ROUNDTRIP_SOURCE_LANGUAGE,
        roundtrip_similarity_threshold: float = DEFAULT_ROUNDTRIP_SIMILARITY_THRESHOLD,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL_NAME,
    ) -> None:
        """Initialize lazy model, tokenizer, and translation quality configuration."""
        self._device = device
        self._tokenizer: Optional[PreTrainedTokenizerBase] = None
        self._model: Optional[PreTrainedModel] = None
        self._model_name = os.path.join(model_root, model_name)
        self._max_input_tokens = max_input_tokens
        self._max_generated_tokens = max_generated_tokens
        self._max_consecutive_repeated_terms = max_consecutive_repeated_terms
        self._roundtrip_validation_enabled = roundtrip_validation_enabled
        self._roundtrip_source_language = roundtrip_source_language
        self._roundtrip_similarity_threshold = roundtrip_similarity_threshold
        self._embedding_model_name = embedding_model_name
        logger.info("Configured translation model at %s", self._model_name)

    @property
    def model(self) -> PreTrainedModel:
        """Return the lazily loaded translation model."""
        if self._model is None:
            logger.info("Loading model from %s on %s", self._model_name, self._device)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(self._model_name).to(
                self._device
            )
            self._model.eval()
        return self._model

    @property
    def tokenizer(self) -> PreTrainedTokenizerBase:
        """Return the lazily loaded translation tokenizer."""
        if self._tokenizer is None:
            logger.info("Loading tokenizer from %s", self._model_name)
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
        return self._tokenizer

    def translate(
        self,
        text: str,
        source: str,
        target: str,
        roundtrip_validation_enabled: Optional[bool] = None,
    ) -> str:
        """Translate text and validate the translated output."""
        translated = self._translate_without_quality_checks(text, source, target)
        self._validate_translation_quality(
            text,
            translated,
            source,
            target,
            roundtrip_validation_enabled,
        )
        return translated

    def _translate_without_quality_checks(self, text: str, source: str, target: str) -> str:
        """Translate text without running recursive quality checks."""
        tokenizer = self.tokenizer
        if hasattr(tokenizer, "src_lang"):
            tokenizer.src_lang = source

        inputs = tokenizer(text, return_tensors="pt").to(self._device)
        self._validate_input_length(inputs)

        translated_tokens = self.model.generate(
            **inputs,
            forced_bos_token_id=self._get_forced_bos_token_id(target),
            max_length=self._max_generated_tokens,
        )
        return tokenizer.batch_decode(
            translated_tokens,
            skip_special_tokens=True,
        )[0]

    def _validate_input_length(self, inputs: BatchEncoding) -> None:
        """Raise an error when tokenized input exceeds the configured limit."""
        input_ids = inputs.get("input_ids")
        token_count = input_ids.shape[-1] if input_ids is not None else 0
        if token_count > self._max_input_tokens:
            raise TranslatorError(
                f"Text too long. Maximum translatable tokens is {self._max_input_tokens}"
                f" but tokenized input contained {token_count} tokens."
                f" This limit has been set because translation quality will strongly degrade."
            )

    def _validate_translation_quality(
        self,
        original_text: str,
        translated_text: str,
        source: str,
        target: str,
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
            translated_text,
            target,
            source,
        )
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

    def _get_forced_bos_token_id(self, target: str) -> int:
        """Resolve the target language code to a forced beginning-of-sentence token ID."""
        tokenizer = self.tokenizer
        lang_code_to_id = getattr(tokenizer, "lang_code_to_id", None)
        if isinstance(lang_code_to_id, dict) and target in lang_code_to_id:
            return int(lang_code_to_id[target])

        token_id = tokenizer.convert_tokens_to_ids(target)
        if token_id is not None and token_id != tokenizer.unk_token_id:
            return int(token_id)

        encoded = tokenizer.encode(target, add_special_tokens=False)
        if encoded:
            return int(encoded[0])

        raise TranslationRequestError(f"Unknown target language code: {target}")


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


def create_translator() -> Translator:
    """Create a translator instance from environment configuration."""
    return Translator(
        model_name=os.environ.get("CTRANSLATE_MODEL_NAME", DEFAULT_MODEL_NAME),
        model_root=os.environ.get("CTRANSLATE_MODEL_ROOT", DEFAULT_MODEL_ROOT),
        device=os.environ.get("CTRANSLATE_DEVICE", "cpu"),
        max_input_tokens=get_env_int(
            "CTRANSLATE_MAX_INPUT_TOKENS",
            DEFAULT_MAX_INPUT_TOKENS,
        ),
        max_generated_tokens=get_env_int(
            "CTRANSLATE_MAX_GENERATED_TOKENS",
            DEFAULT_MAX_GENERATED_TOKENS,
        ),
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
        roundtrip_validation_enabled = get_roundtrip_validation_override()
        return jsonify(
            {
                "translated": translator.translate(
                    text,
                    source,
                    target,
                    roundtrip_validation_enabled=roundtrip_validation_enabled,
                )
            }
        )
    except TranslationRequestError as error:
        return jsonify({"error": str(error)}), 400
    except TranslatorError as error:
        return jsonify({"error": str(error)}), 400
    except TranslationQualityError as error:
        logger.warning("Translation quality validation failed: %s", error)
        return jsonify({"error": str(error)}), 502
    except RuntimeError as error:
        logger.exception("Translation failed")
        return jsonify({"error": str(error)}), 500


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the HTTP server."""
    parser = argparse.ArgumentParser(description="Run the Transformers translation API.")
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
    logger.info("Serving Transformers translation API on port %s", args.port)
    http_server.serve_forever()


if __name__ == "__main__":
    main()
