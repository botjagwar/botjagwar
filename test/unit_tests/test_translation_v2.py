from unittest.case import TestCase

from api.translation_v2.functions import \
    translate_using_bridge_language


class TestTranslationV2(TestCase):
    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_translation_using_bridge_language(self):
        translate_using_bridge_language('ana', 'ka', 'mg')

    def test_translate_using_convergent_definition(self):
        pass

    def test__save_translation_from_page(self):
        pass

    def test_generate_summary(self):
        pass


