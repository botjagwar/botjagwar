"""Minimal OpenAI-compatible chat client used by the page checking agent."""
from __future__ import annotations

import configparser
import json
import logging
from typing import Any, Dict, List, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_random_exponential

from api.config import BotjagwarConfig

log = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"


class DeepSeekClient:
    """Client for DeepSeek or a configured OpenAI-compatible local service."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        api_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Initialize the client with an API key and model.

        The key and model are read from the Botjagwar configuration when not
        provided explicitly, allowing callers to inject them for testing.

        Args:
            api_key: Model service API key. Defaults to the configured key.
            model: Model name sent to the service. Defaults to the configured model.
            api_url: Chat completions URL. Defaults to the configured URL or DeepSeek.
            session: Optional requests session for dependency injection.
        """
        config = BotjagwarConfig()
        configured_api_key = self._optional_config(
            config, "page_checker_model_api_key"
        )
        self.api_key = (
            api_key
            if api_key is not None
            else configured_api_key
            if configured_api_key is not None
            else config.get("deepseek_api_key", "global")
        )
        configured_model = self._optional_config(config, "page_checker_model")
        self.model = (
            model
            if model is not None
            else configured_model
            if configured_model
            else config.get("deepseek_model", "global")
        )
        self.api_url = (
            api_url
            if api_url is not None
            else self._optional_config(config, "page_checker_model_api_url")
            or DEEPSEEK_API_URL
        )
        self._session = session if session is not None else requests.Session()

    @staticmethod
    def _optional_config(config: BotjagwarConfig, key: str) -> Optional[str]:
        """Return an optional global setting without changing legacy config behavior."""
        try:
            return config.get(key, "global").strip()
        except (KeyError, configparser.Error):
            return None

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
    ) -> str:
        """Send a prompt to the DeepSeek chat completions API.

        Args:
            prompt: The user message to send to the model.
            system_prompt: Optional system message.
            json_mode: Whether to request a structured JSON response.

        Returns:
            The raw text content of the model answer.

        Raises:
            RuntimeError: When the API key is missing or the request fails.
        """
        if not self.api_key and self.api_url == DEEPSEEK_API_URL:
            raise RuntimeError(
                "DeepSeek API key is not set. Add 'deepseek_api_key' to "
                "conf/config.ini (or ~/.config/botjagwar/config.ini)."
            )

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {"model": self.model, "messages": messages}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
            payload["temperature"] = 0

        headers = (
            {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        )
        try:
            response = self._session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            log.error("DeepSeek API request failed: %s", exc)
            raise RuntimeError(f"DeepSeek API request failed: {exc}") from exc

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Unexpected DeepSeek API response: {data}"
            ) from exc

    def complete_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a prompt and parse the answer as a JSON object.

        Args:
            prompt: The user message to send to the model.
            system_prompt: Optional system message.

        Returns:
            The parsed JSON object from the model answer.

        Raises:
            ValueError: When the answer is not valid JSON.
        """
        text = self.complete(prompt, system_prompt=system_prompt, json_mode=True)
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[len("json"):]
            cleaned = cleaned.strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            log.error("DeepSeek answer is not valid JSON: %s", cleaned)
            raise ValueError(f"DeepSeek answer is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("DeepSeek answer must be a JSON object.")
        return parsed
