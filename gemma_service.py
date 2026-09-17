#!/usr/bin/env python3
"""Serve a local GGUF instruction model through a small chat API."""

from __future__ import annotations

import argparse
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request
from gevent.pywsgi import WSGIServer


DEFAULT_MODEL_PATH = "/opt/gemma/model"
DEFAULT_PORT = 8891
DEFAULT_MAX_TOKENS = 1024
DEFAULT_CONTEXT_TOKENS = 4096

logger = logging.getLogger(__name__)
app = Flask(__name__)


class ChatRequestError(ValueError):
    """Raised when a chat completion request is invalid."""


def get_env_int(name: str, default: int) -> int:
    """Return a positive integer environment setting or its default."""
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        raise RuntimeError(f"{name} must be an integer.") from None
    if parsed < 1:
        raise RuntimeError(f"{name} must be greater than zero.")
    return parsed


class GemmaRuntime:
    """Lazily load and run a local GGUF model through llama.cpp."""

    def __init__(self, model_path: str, device: str, max_tokens: int) -> None:
        """Store inference configuration without loading model dependencies."""
        self.model_path = model_path
        self.device = device
        self.max_tokens = max_tokens
        self._model: Any = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _model_file(self) -> Path:
        """Resolve one GGUF file from the configured file or directory."""
        model_path = Path(self.model_path)
        if model_path.is_file():
            return model_path
        candidates = sorted(model_path.glob("*.gguf")) if model_path.is_dir() else []
        if len(candidates) != 1:
            raise RuntimeError(
                f"Gemma model path must be a GGUF file or a directory containing exactly one GGUF file: {model_path}"
            )
        return candidates[0]

    def _load(self) -> Any:
        """Load the GGUF model from local files on first use."""
        if self._model is not None:
            return self._model

        with self._load_lock:
            if self._model is not None:
                return self._model
            model_file = self._model_file()
            try:
                from llama_cpp import Llama
            except ImportError as error:
                raise RuntimeError(
                    "Gemma model dependencies are unavailable; install requirements-gemma.txt."
                ) from error

            gpu_layers = 0 if self.device == "cpu" else -1
            try:
                model = Llama(
                    model_path=str(model_file),
                    n_ctx=max(DEFAULT_CONTEXT_TOKENS, self.max_tokens + 2048),
                    n_gpu_layers=gpu_layers,
                    verbose=False,
                )
            except (OSError, RuntimeError, TypeError, ValueError) as error:
                raise RuntimeError(f"Unable to load local GGUF model {model_file}: {error}") from error

            self._model = model
            logger.info("Loaded local GGUF instruction model from %s on %s", model_file, self.device)
        return self._model

    def generate(self, messages: list[dict[str, str]], temperature: float) -> str:
        """Generate one assistant response for a text-only chat conversation."""
        model = self._load()
        with self._inference_lock:
            response = model.create_chat_completion(
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=temperature,
            )
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("GGUF model returned an invalid chat completion response.") from error
        if not isinstance(content, str):
            raise RuntimeError("GGUF model returned chat completion content that is not text.")
        return content.strip()


def _configured_runtime() -> GemmaRuntime:
    """Create an unloaded runtime from environment defaults."""
    return GemmaRuntime(
        os.environ.get("GEMMA_MODEL_PATH", DEFAULT_MODEL_PATH),
        os.environ.get("GEMMA_DEVICE", "auto"),
        get_env_int("GEMMA_MAX_TOKENS", DEFAULT_MAX_TOKENS),
    )


runtime = _configured_runtime()


def _request_values() -> tuple[str, list[dict[str, str]], float]:
    """Validate and return supported chat completion request values."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ChatRequestError("Request body must be a JSON object.")

    model = payload.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ChatRequestError("model must be a non-empty string.")
    raw_messages = payload.get("messages")
    if not isinstance(raw_messages, list) or not raw_messages:
        raise ChatRequestError("messages must be a non-empty list.")

    messages: list[dict[str, str]] = []
    for message in raw_messages:
        if not isinstance(message, dict):
            raise ChatRequestError("Each message must be an object.")
        role = message.get("role")
        content = message.get("content")
        if role not in {"system", "user", "assistant"}:
            raise ChatRequestError("Each message role must be system, user, or assistant.")
        if not isinstance(content, str) or not content.strip():
            raise ChatRequestError("Each message must contain non-empty text content.")
        messages.append({"role": role, "content": content})

    temperature = payload.get("temperature", 0)
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
        raise ChatRequestError("temperature must be a number.")
    temperature = float(temperature)
    if not 0 <= temperature <= 2:
        raise ChatRequestError("temperature must be between 0 and 2.")

    response_format = payload.get("response_format")
    if response_format is not None:
        if not isinstance(response_format, dict) or response_format.get("type") not in {"text", "json_object"}:
            raise ChatRequestError("response_format.type must be text or json_object.")
    return model.strip(), messages, temperature


@app.get("/health")
def health() -> Any:
    """Return health without loading the model."""
    return jsonify({"status": "ok"})


@app.post("/v1/chat/completions")
def chat_completions() -> Any:
    """Generate one OpenAI-compatible chat completion response."""
    try:
        model, messages, temperature = _request_values()
        content = runtime.generate(messages, temperature)
    except ChatRequestError as error:
        return jsonify({"error": {"message": str(error), "type": "invalid_request_error"}}), 400
    except RuntimeError as error:
        logger.exception("Local model inference failed")
        return jsonify({"error": {"message": str(error), "type": "server_error"}}), 500

    return jsonify(
        {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        }
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse local model and HTTP server configuration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=get_env_int("GEMMA_PORT", DEFAULT_PORT))
    parser.add_argument("--model-path", default=os.environ.get("GEMMA_MODEL_PATH", DEFAULT_MODEL_PATH))
    parser.add_argument("--device", default=os.environ.get("GEMMA_DEVICE", "auto"))
    parser.add_argument("--max-tokens", type=int, default=get_env_int("GEMMA_MAX_TOKENS", DEFAULT_MAX_TOKENS))
    return parser.parse_args(argv)


def main() -> None:
    """Start the chat completion server on all IPv4 interfaces."""
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    args = parse_args()
    if args.port < 1 or args.max_tokens < 1:
        raise SystemExit("port and max-tokens must be greater than zero")
    global runtime
    runtime = GemmaRuntime(args.model_path, args.device, args.max_tokens)
    logger.info("Serving local Gemma API on 0.0.0.0:%s", args.port)
    WSGIServer(("0.0.0.0", args.port), app).serve_forever()


if __name__ == "__main__":
    main()
