import unittest
from unittest.mock import patch

from api.servicemanager.nllb import (
    NllbDefinitionTranslation,
    DefinitionTranslationError,
)


class TestNllbDefinitionTranslation(unittest.TestCase):

    @patch("api.servicemanager.nllb.requests.get")
    def test_get_translation_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"translated": "Bonjour"}

        nllb = NllbDefinitionTranslation("fr")
        nllb.translation_server = "localhost:12020"
        result = nllb.get_translation("Hello")
        self.assertEqual(result, "Bonjour")

        expected_url = "http://localhost:12020/translate/fra_Latn/eng_Latn"
        expected_params = {"text": "Hello"}
        mock_get.assert_called_once_with(expected_url, params=expected_params)

    @patch("api.servicemanager.nllb.requests.get")
    def test_get_translation_failure(self, mock_get):
        mock_get.return_value.status_code = 404
        mock_get.return_value.text = "Not Found"

        nllb = NllbDefinitionTranslation("fr")
        with self.assertRaises(DefinitionTranslationError):
            nllb.get_translation("Hello")
