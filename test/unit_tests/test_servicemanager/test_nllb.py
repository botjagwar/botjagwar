import unittest
from unittest.mock import MagicMock, patch

import requests

from api.servicemanager.nllb import (
    NllbDefinitionTranslation,
    DefinitionTranslationError,
)
from api.http_client import DEFAULT_HTTP_TIMEOUT, NLLB_HTTP_TIMEOUT


class TestNllbDefinitionTranslation(unittest.TestCase):

    @patch("api.servicemanager.nllb.requests.get")
    def test_get_translation_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"translated": "Bonjour"}

        nllb = NllbDefinitionTranslation("fr")
        nllb.translation_server = "localhost:12020"
        result = nllb.get_nllb_translation("Hello")
        self.assertEqual(result, "Bonjour")

        expected_url = "http://localhost:12020/translate/eng_Latn/fra_Latn"
        expected_params = {"text": "Hello"}
        mock_get.assert_called_once_with(
            expected_url, params=expected_params, timeout=NLLB_HTTP_TIMEOUT
        )

    @patch("api.servicemanager.nllb.requests.get")
    def test_get_translation_forwards_roundtrip_override(self, mock_get):
        """The entry-translator setting reaches the standalone NLLB service."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"translated": "Bonjour"}
        nllb = NllbDefinitionTranslation("fr")
        nllb.translation_server = "localhost:12020"

        result = nllb.get_nllb_translation(
            "Hello",
            roundtrip_validation_enabled=False,
        )

        self.assertEqual(result, "Bonjour")
        mock_get.assert_called_once_with(
            "http://localhost:12020/translate/eng_Latn/fra_Latn",
            params={"text": "Hello", "roundtrip_validation": "false"},
            timeout=NLLB_HTTP_TIMEOUT,
        )

    @patch("api.servicemanager.nllb.requests.get")
    def test_get_translation_failure(self, mock_get):
        mock_get.return_value.status_code = 404
        mock_get.return_value.text = "Not Found"

        nllb = NllbDefinitionTranslation("fr")
        with self.assertRaises(DefinitionTranslationError):
            nllb.get_translation("Hello")

    @patch("api.servicemanager.nllb.requests.post")
    @patch("api.servicemanager.nllb.requests.get")
    def test_get_translation_stores_cache_row_without_online_vector(
        self, mock_get, mock_post
    ):
        """Cache misses are stored without loading an embedding model."""
        cache_miss = MagicMock()
        cache_miss.status_code = 200
        cache_miss.json.return_value = []

        nllb_response = MagicMock()
        nllb_response.status_code = 200
        nllb_response.json.return_value = {"translated": "Bonjour"}

        mock_get.side_effect = [cache_miss, nllb_response]
        mock_post.return_value.status_code = 201

        nllb = NllbDefinitionTranslation("fr")
        nllb.postgrest_server = "localhost:3000"
        nllb.translation_server = "localhost:12020"
        result = nllb.get_translation("Hello")

        self.assertEqual(result, "Bonjour")
        mock_post.assert_called_once_with(
            "http://localhost:3000/nllb_translations",
            json={
                "sentence": "Hello",
                "translation": "Bonjour",
                "source_language": "eng_Latn",
                "target_language": "fra_Latn",
            },
            timeout=DEFAULT_HTTP_TIMEOUT,
        )

    @patch("api.servicemanager.nllb.requests.post")
    @patch("api.servicemanager.nllb.requests.get")
    def test_cache_read_failure_falls_back_to_translation(
        self, mock_get, mock_post
    ) -> None:
        """An unavailable cache does not prevent the required NLLB call."""
        nllb_response = MagicMock(status_code=200)
        nllb_response.json.return_value = {"translated": "Bonjour"}
        mock_get.side_effect = [requests.ConnectionError("cache down"), nllb_response]
        mock_post.return_value.status_code = 201
        nllb = NllbDefinitionTranslation("fr")
        nllb.postgrest_server = "localhost:3000"
        nllb.translation_server = "localhost:12020"

        assert nllb.get_translation("Hello") == "Bonjour"

    @patch("api.servicemanager.nllb.requests.post")
    @patch("api.servicemanager.nllb.requests.get")
    def test_cache_write_failure_does_not_discard_translation(
        self, mock_get, mock_post
    ) -> None:
        """A completed translation is returned when its cache write fails."""
        cache_miss = MagicMock(status_code=200)
        cache_miss.json.return_value = []
        nllb_response = MagicMock(status_code=200)
        nllb_response.json.return_value = {"translated": "Bonjour"}
        mock_get.side_effect = [cache_miss, nllb_response]
        mock_post.side_effect = requests.ConnectionError("cache down")
        nllb = NllbDefinitionTranslation("fr")
        nllb.postgrest_server = "localhost:3000"
        nllb.translation_server = "localhost:12020"

        assert nllb.get_translation("Hello") == "Bonjour"

    @patch("api.servicemanager.nllb.requests.post")
    @patch("api.servicemanager.nllb.requests.get")
    def test_disabled_roundtrip_translation_is_not_cached(
        self, mock_get, mock_post
    ) -> None:
        """Unvalidated output cannot be reused after validation is enabled again."""
        cache_miss = MagicMock(status_code=200)
        cache_miss.json.return_value = []
        nllb_response = MagicMock(status_code=200)
        nllb_response.json.return_value = {"translated": "Bonjour"}
        mock_get.side_effect = [cache_miss, nllb_response]
        nllb = NllbDefinitionTranslation("fr")
        nllb.postgrest_server = "localhost:3000"
        nllb.translation_server = "localhost:12020"

        assert nllb.get_translation(
            "Hello",
            roundtrip_validation_enabled=False,
        ) == "Bonjour"
        mock_post.assert_not_called()

    @patch("api.servicemanager.nllb.requests.post")
    @patch("api.servicemanager.nllb.requests.get")
    def test_echo_translation_is_not_cached(self, mock_get, mock_post) -> None:
        """A server response that copies the source text is never cached."""
        cache_miss = MagicMock(status_code=200)
        cache_miss.json.return_value = []
        nllb_response = MagicMock(status_code=200)
        nllb_response.json.return_value = {"translated": "Hello"}
        mock_get.side_effect = [cache_miss, nllb_response]

        nllb = NllbDefinitionTranslation("fr")
        nllb.postgrest_server = "localhost:3000"
        nllb.translation_server = "localhost:12020"
        assert nllb.get_translation("Hello") == ""
        mock_post.assert_not_called()

    @patch("api.servicemanager.nllb.requests.get")
    def test_echo_cached_translation_is_ignored(self, mock_get) -> None:
        """A cached verbatim copy of the source is not returned."""
        cache_hit = MagicMock(status_code=200)
        cache_hit.json.return_value = [
            {"translation": "Hello", "source_language": "eng_Latn", "target_language": "fra_Latn"}
        ]
        nllb_response = MagicMock(status_code=200)
        nllb_response.json.return_value = {"translated": "Bonjour"}
        mock_get.side_effect = [cache_hit, nllb_response]

        nllb = NllbDefinitionTranslation("fr")
        nllb.postgrest_server = "localhost:3000"
        nllb.translation_server = "localhost:12020"
        assert nllb.get_translation("Hello") == "Bonjour"
