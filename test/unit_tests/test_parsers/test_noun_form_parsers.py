from unittest import TestCase
from unittest.mock import patch

import mwparserfromhell

from api.parsers.functions import parse_el_form_of
from api.parsers.functions import parse_hu_inflection_of
from api.parsers.functions import parse_inflection_of
from api.parsers.functions.noun_forms import definitions as noun_form_definitions
from api.parsers.functions.noun_forms.definitions import parameterized_parse_fr_definition
from api.parsers.functions.noun_forms.templates import parse_et_form_of
from api.parsers.functions.noun_forms.templates import (
    parse_fi_form_of as parse_fi_form_of_noun,
)
from api.parsers.functions.noun_forms.templates import parse_lt_noun_form
from api.parsers.functions.noun_forms.templates import parse_nl_noun_form_of
from api.parsers.inflection_template import AdjectiveForm, NounForm


class TestNounFormParsersDefinition(TestCase):
    """Test French definition-line parsing for noun-like forms."""

    def test_parse_fr_definition_extracts_grammatical_features(self) -> None:
        """A marked-up definition produces normalized grammatical fields."""

        definition = (
            "''Forme accusative de la deuxième personne du pluriel féminin défini de'' "
            "{{lien|maison|fr}}."
        )

        output = parameterized_parse_fr_definition()(definition)

        self.assertIsInstance(output, NounForm)
        self.assertEqual(output.lemma, "maison")
        self.assertEqual(output.case, "accusative")
        self.assertEqual(output.number, "plural")
        self.assertEqual(output.person, "second-person")
        self.assertEqual(output.definiteness, "definite")
        self.assertEqual(output.gender, "feminine")

    def test_parse_fr_definition_defaults_number_and_uses_wikilink_target(self) -> None:
        """An omitted number defaults to singular and link labels do not become lemmas."""

        output = parameterized_parse_fr_definition()(
            "''Forme nominative masculine de'' [[chat|chats]]."
        )

        self.assertEqual(output.lemma, "chat")
        self.assertEqual(output.case, "nominative")
        self.assertEqual(output.number, "singular")
        self.assertEqual(output.gender, "masculine")

    def test_parse_fr_definition_accepts_wikicode_and_requested_form_class(self) -> None:
        """Pre-parsed definitions avoid reparsing and retain the requested output type."""

        definition_code = mwparserfromhell.parse(
            "''Forme partitive duelle neutre de l’'' {{lien|lang=fr|1=heureux}}."
        )

        output = parameterized_parse_fr_definition(AdjectiveForm)(definition_code)

        self.assertIsInstance(output, AdjectiveForm)
        self.assertEqual(output.lemma, "heureux")
        self.assertEqual(output.case, "partitive")
        self.assertEqual(output.number, "dual")
        self.assertEqual(output.gender, "neutral")

    def test_parse_fr_definition_prefers_lien_and_skips_empty_parameters(self) -> None:
        """A valid lien lemma wins over links and empty positional parameters."""

        output = parameterized_parse_fr_definition()(
            "''Pluriel de'' [[solution de repli]] {{lien||lemme principal|fr}}."
        )

        self.assertEqual(output.lemma, "lemme principal")
        self.assertEqual(output.number, "plural")

    def test_parse_fr_definition_falls_back_from_empty_lien_to_wikilink(self) -> None:
        """A lien without a positional lemma does not hide a usable wikilink."""

        output = parameterized_parse_fr_definition()(
            "''Singulier de'' {{lien|lang=fr}} [[secours|forme affichée]]."
        )

        self.assertEqual(output.lemma, "secours")
        self.assertEqual(output.number, "singular")

    def test_parse_fr_definition_supports_configured_possessiveness(self) -> None:
        """Configured possessiveness markers are copied to the parsed form."""

        with patch.dict(
            noun_form_definitions.POSSESSIVENESS,
            {"marque-x": "first-person singular"},
        ):
            output = parameterized_parse_fr_definition()(
                "''Forme marque-x de'' [[maison]]."
            )

        self.assertEqual(output.lemma, "maison")
        self.assertEqual(output.possessiveness, "first-person singular")

    def test_parse_fr_definition_handles_text_without_a_lemma(self) -> None:
        """Unlinked text returns an empty lemma while preserving safe defaults."""

        output = parameterized_parse_fr_definition()("Forme non reconnue.")

        self.assertEqual(output.lemma, "")
        self.assertEqual(output.number, "singular")
        self.assertIsNone(output.case)
        self.assertIsNone(output.gender)


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
