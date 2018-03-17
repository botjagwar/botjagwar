from unittest.case import TestCase

from unknown_language_manager import translate_language_name

class TestUnknownLanguageManager(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_translate_language_name(self):
        translated = translate_language_name('toninu')
        self.assertEquals(translated, 'tônino')
        translated = translate_language_name('tanana')
        self.assertEquals(translated, 'tanana')
        translated = translate_language_name('chanki')
        self.assertEquals(translated, 'tsanky')
        self.assertRaises(ValueError, translate_language_name, 'tenia nanani')