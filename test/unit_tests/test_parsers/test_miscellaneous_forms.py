from unittest import TestCase

from api.parsers.functions import parse_romanization_template


class TestRomanizations(TestCase):
    def test_parse_romanization_case_1(self):
        template_expression = '{{romanization of|got|𐍃𐍅𐌹𐌺𐌿𐌽𐌸}}'
        fct = parse_romanization_template(2)
        form_of = fct(template_expression)
        self.assertEquals(form_of.lemma, '𐍃𐍅𐌹𐌺𐌿𐌽𐌸')

    def test_parse_romanization_case_2(self):
        template_expression = '{{alternative spelling of|cmn|bèng}}'
        fct = parse_romanization_template(2)
        form_of = fct(template_expression)
        self.assertEquals(form_of.lemma, 'bèng')

    def test_parse_romanization_case_3(self):
        template_expression = '{{pinyin reading of|變化多端|变化多端}}'
        fct = parse_romanization_template(1)
        form_of = fct(template_expression)
        self.assertEquals(form_of.lemma, '變化多端')


    def test_parse_romanization_case_4(self):
        template_expression = '{{ja-romanization of|アフターバーナー}}'
        fct = parse_romanization_template(1)
        form_of = fct(template_expression)
        self.assertEquals(form_of.lemma, 'アフターバーナー')

    def test_parse_romanization_case_5(self):
        template_expression = '{{romanization of|mnc|ᡝᡵᡝ ᠴᡳᠮᠠᡵᡳ}}'
        fct = parse_romanization_template(2)
        form_of = fct(template_expression)
        self.assertEquals(form_of.lemma, 'ᡝᡵᡝ ᠴᡳᠮᠠᡵᡳ')

    def test_parse_romanization_case_6(self):
        template_expression = '{romanization of|ban|ᬲᬵᬫ᭄ᬧᬸᬦ᭄}}'
        fct = parse_romanization_template(2)
        form_of = fct(template_expression)
        self.assertEquals(form_of.lemma, 'ᬲᬵᬫ᭄ᬧᬸᬦ᭄')

    def test_parse_romanization_case_7(self):
        template_expression = '{{egy-alt|ḥpt|type=Manuel de Codage}}'
        fct = parse_romanization_template(1)
        form_of = fct(template_expression)
        self.assertEquals(form_of.lemma, 'ḥpt')

    def test_parse_romanization_case_8(self):
        template_expression = '{{romanization of|su|ᮃᮙ᮪ᮘᮨᮊᮔ᮪}}'
        fct = parse_romanization_template(2)
        form_of = fct(template_expression)
        self.assertEquals(form_of.lemma, 'ᮃᮙ᮪ᮘᮨᮊᮔ᮪')

    def test_parse_romanization_case_9(self):
        template_expression = '{{ryu-romanization of|モンゴル}}'
        fct = parse_romanization_template(1)
        form_of = fct(template_expression)
        self.assertEquals(form_of.lemma, 'モンゴル')
