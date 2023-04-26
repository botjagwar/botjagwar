import unittest
from unittest.mock import patch

from api.servicemanager.pgrest import TemplateTranslation


class TestTemplateTranslation(unittest.TestCase):

    def setUp(self):
        self.template_translation = TemplateTranslation(use_postgrest=False)

    @patch('api.servicemanager.pgrest.requests.get')
    def test_get_mapped_template_in_database_with_online_backend(self, mock_requests):
        mock_requests.return_value.status_code = 200
        mock_requests.return_value.json.return_value = {'target_template': 'target_template'}

        self.template_translation.online = True

        mapped_template = self.template_translation.get_mapped_template_in_database('source_template')
        self.assertEqual(mapped_template, 'target_template')

    @patch('api.servicemanager.pgrest.requests.get')
    def test_get_mapped_template_in_database_with_offline_backend(self, mock_requests):
        self.template_translation.online = False

        mapped_template = self.template_translation.get_mapped_template_in_database('source_template')
        self.assertIsNone(mapped_template)

    @patch('api.servicemanager.pgrest.requests.get')
    def test_get_mapped_template_in_database_with_http_error(self, mock_requests):
        mock_requests.return_value.status_code = 500
        mock_requests.return_value.text = 'Internal Server Error'

        self.template_translation.online = True

        with self.assertRaises(Exception) as context:
            self.template_translation.get_mapped_template_in_database('source_template')

        self.assertIn('Unexpected error', str(context.exception))

    @patch('api.servicemanager.pgrest.requests.post')
    def test_add_translated_title_with_online_backend(self, mock_requests):
        mock_requests.return_value.status_code = 200

        self.template_translation.online = True

        result = self.template_translation.add_translated_title(
            'source_template', 'translated_title', 'en', 'mg')

        self.assertIsNone(result)

    @patch('api.servicemanager.pgrest.requests.post')
    def test_add_translated_title_with_http_error(self, mock_requests):
        mock_requests.return_value.status_code = 400
        mock_requests.return_value.text = 'Bad Request'

        self.template_translation.online = True

        with self.assertRaises(Exception) as context:
            self.template_translation.add_translated_title(
                'source_template', 'translated_title', 'en', 'mg')

        self.assertIn('Unexpected error', str(context.exception))
