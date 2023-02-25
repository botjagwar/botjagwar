from unittest.case import TestCase

from parameterized import parameterized

from unknown_language_manager import translate_language_name

language_tuples = [
    ('toninu', 'tônino'),
    ('tanana', 'tanana'),
    ('chanki', 'tsanky'),
    ('zanja', 'zanja'),
    ('chirque', 'tsirke'),
    ('kuyney', 'koiney'),
    ('chanki', 'tsanky'),
    ('choctaw', 'tsôktao'),
    ('lakota', 'lakôta'),
    ('yuchi', 'iotsy'),
    ('makwa', 'makoa'),
    ('maxiyan', 'maksiian'),
    ('mixtec', 'mikstek'),
]

error_language_tuples = [
    ('tenia nanani',)
]


class TestUnknownLanguageManager(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @parameterized.expand(language_tuples)
    def test_translate_language_name(self, language_name, malagasy_name):
        translated = translate_language_name(language_name)
        self.assertEqual(translated, malagasy_name)
        translated = translate_language_name(language_name)
        self.assertEqual(translated, malagasy_name)
        translated = translate_language_name(language_name)
        self.assertEqual(translated, malagasy_name)

    @parameterized.expand(error_language_tuples)
    def test_translate_language_name_with_error(self, language_name):
        self.assertRaises(ValueError, translate_language_name, language_name)
