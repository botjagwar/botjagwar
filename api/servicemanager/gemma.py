"""Client for generating English definitions with the local Gemma service."""
from __future__ import annotations

import configparser
import json
from typing import Any, Optional

import requests

from api.config import BotjagwarConfig
from api.http_client import BULK_HTTP_TIMEOUT


DEFAULT_API_URL = "http://127.0.0.1:8891/v1/chat/completions"
DEFAULT_MODEL = "gemma-4-e2b-it-q4-k-m"


class GemmaDefinitionReformulator:
    """Generate or reformulate English definitions with the local Gemma service."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Initialize the client with injectable connection details."""
        config = BotjagwarConfig()
        self.api_url = api_url or self._optional_config(config, "api_url") or DEFAULT_API_URL
        self.model = model or self._optional_config(config, "model") or DEFAULT_MODEL
        self.api_key = (
            api_key
            if api_key is not None
            else self._optional_config(config, "api_key") or ""
        )
        self._session = session if session is not None else requests.Session()

    @staticmethod
    def _optional_config(config: BotjagwarConfig, key: str) -> Optional[str]:
        """Return an optional Gemma setting."""
        try:
            return config.get(key, "gemma").strip()
        except (KeyError, configparser.Error):
            return None

    def reformulate(self, definition: str) -> str:
        """Return a meaning-preserving definition written in simple English."""
        system_prompt = (
            "Rewrite English dictionary definitions using simple, common English "
            "words while preserving the exact meaning. Return only the rewritten "
            "definition, with no explanation or quotation marks."
        )
        try:
            return self._complete(definition, system_prompt)
        except RuntimeError as exc:
            raise RuntimeError(f"Gemma definition reformulation failed: {exc}") from exc

    def complete_json(self, prompt: str, system_prompt: Optional[str] = None) -> dict[str, Any]:
        """Return one structured definition-generation response from Gemma."""
        text = self._complete(prompt, system_prompt, json_mode=True)
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[len("json"):]
            cleaned = cleaned.strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Gemma answer is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Gemma answer must be a JSON object.")
        return parsed

    def _complete(
        self,
        prompt: str,
        system_prompt: Optional[str],
        *,
        json_mode: bool = False,
    ) -> str:
        """Send one deterministic chat request to the configured Gemma service."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            "messages": messages,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = (
            {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        )
        try:
            response = self._session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=BULK_HTTP_TIMEOUT,
            )
            response.raise_for_status()
            generated = response.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Gemma request failed: {exc}") from exc
        if not isinstance(generated, str) or not generated.strip():
            raise RuntimeError("Gemma request returned empty text.")
        return generated.strip()


__all__ = ["GemmaDefinitionReformulator"]
