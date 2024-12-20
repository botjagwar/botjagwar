from unittest import TestCase

from api.parsers.functions import parse_el_form_of
from api.parsers.functions import parse_hu_inflection_of
from api.parsers.functions import parse_inflection_of
from api.parsers.functions.noun_forms.templates import parse_et_form_of
from api.parsers.functions.noun_forms.templates import (
    parse_fi_form_of as parse_fi_form_of_noun,
)
from api.parsers.functions.noun_forms.templates import parse_lt_noun_form
from api.parsers.functions.noun_forms.templates import parse_nl_noun_form_of
from api.parsers.inflection_template import NounForm


class TestNounFormParsers(TestCase):

    def test_parse_inflection_of_noun_form(self):
        template_expression = "{{inflection of|abdominal||p|lang=es}}"
        func = parse_inflection_of(NounForm)
        output = func(template_expression)
        self.assertIsInstance(output, NounForm)
        self.assertEqual(output.lemma, "abdominal")
        self.assertEqual(output.number, "p")

    def test_parse_inflection_of_noun_form_2(self):
        template_expression = "{{inflection of|de|Schrödingergleichung||p}}"
        func = parse_inflection_of(NounForm)
        output = func(template_expression)
        self.assertIsInstance(output, NounForm)
        self.assertEqual(output.lemma, "Schrödingergleichung")
        self.assertEqual(output.number, "p")

    def test_parse_fi_form_of_noun(self):
        template_expression = "{{fi-form of|näverrin|case=nominative|pl=plural}}"
        output = parse_fi_form_of_noun(template_expression)
        self.assertIsInstance(output, NounForm)
        self.assertEqual(output.case, "nominative")
        self.assertEqual(output.number, "plural")
        self.assertEqual(output.lemma, "näverrin")

    def test_parse_nl_noun_form_of_plural(self):
        template_expression = "{{nl-noun form of|pl|aanbouwing}}"
        output = parse_nl_noun_form_of(template_expression)
        self.assertEqual(output.number, "pl")
        self.assertEqual(output.lemma, "aanbouwing")

    def test_parse_nl_noun_form_of_diminutive(self):
        template_expression = "{{nl-noun form of|dim|aanbiedingsfolder}}"
        output = parse_nl_noun_form_of(template_expression)
        self.assertEqual(output.number, "s")
        self.assertEqual(output.case, "dim")
        self.assertEqual(output.lemma, "aanbiedingsfolder")

    def test_parse_nl_noun_form_of_genitive(self):
        template_expression = "{{nl-noun form of|gen|land}}"
        output = parse_nl_noun_form_of(template_expression)
        self.assertEqual(output.number, "s")
        self.assertEqual(output.case, "gen")
        self.assertEqual(output.lemma, "land")

    def test_parse_lt_noun_form_of(self):
        template_expression = "{{lt-form-noun|d|s|abatė}}"
        output = parse_lt_noun_form(template_expression)
        self.assertEqual(output.number, "s")
        self.assertEqual(output.case, "d")
        self.assertEqual(output.lemma, "abatė")

    def test_parse_el_form_of_noun(self):
        template_expression = "{{el-form-of-nounadj|αβοκέτα|c=gen|n=s}}"
        output = parse_el_form_of(NounForm)(template_expression)
        self.assertIsInstance(output, NounForm)
        self.assertEqual(output.number, "s")
        self.assertEqual(output.case, "gen")
        self.assertEqual(output.lemma, "αβοκέτα")

    def test_parse_hu_inflection_of(self):
        template_expression = "{{hu-inflection of|sors|ill|s}}"
        output = parse_hu_inflection_of(template_expression)
        self.assertEqual(output.number, "s")
        self.assertEqual(output.case, "ill")
        self.assertEqual(output.lemma, "sors")

    def test_parse_et_form_of(self):
        template_expression = "{{et-nom form of|pos=noun|c=nom|n=pl|jalalaba}}"
        output = parse_et_form_of(template_expression)
        self.assertEqual(output.number, "pl")
        self.assertEqual(output.case, "nom")
        self.assertEqual(output.lemma, "jalalaba")
