from unittest import TestCase

from parameterized import parameterized

from api.parsers.functions.verb_forms.definitions import parse_fr_definition
from api.parsers.functions.verb_forms.templates import parse_ca_verb_form_of
from api.parsers.functions.verb_forms.templates import parse_de_verb_form_of
from api.parsers.functions.verb_forms.templates import parse_es_compound_of
from api.parsers.functions.verb_forms.templates import parse_es_verb_form_of
from api.parsers.functions.verb_forms.templates import parse_fi_form_of
from api.parsers.functions.verb_forms.templates import parse_fi_verb_form_of
from api.parsers.functions.verb_forms.templates import parse_la_verb_form_inflection_of
from api.parsers.functions.verb_forms.templates import parse_verb_form_inflection_of
from api.parsers.inflection_template import VerbForm


class TestVerbFormParsersDefinition(TestCase):
    fr_verb_forms = [
        "''Première personne du pluriel du conditionnel présent du verbe'' [[fermenter]].",
        "''Première personne du singulier du présent de l’indicatif de'' [[fermer]].",
        "''Première personne du singulier du présent du subjonctif de'' [[fermer]].",
        "''Première personne du pluriel du présent du subjonctif de'' [[clore]].",
        "''Deuxième personne du singulier de l’impératif présent de'' [[fermer]].",
        "''Deuxième personne du singulier de l’impératif de'' {{lien|acentuar|pt}}.",
        "''Troisième personne du singulier du présent de l’indicatif de'' {{lien|acentuar|pt}}.",
        "''Troisième personne du singulier de l’indicatif présent de'' [[clore]].",
        "''Troisième personne du singulier du présent de l’indicatif de'' [[fermer]].",
        "''Troisième personne du singulier du présent du subjonctif de'' [[fermer]].",
        "''Troisième personne du singulier du futur de'' [[fermer]].",
        "''Troisième personne du pluriel de l’imparfait du subjonctif du verbe'' [[fermer]].",
        "''Troisième personne du singulier du passé simple de'' [[fermer]].",
        "''Troisième personne du pluriel du conditionnel présent de'' [[fermer]].",
    ]

    @parameterized.expand(fr_verb_forms)
    def test_parse_fr_definition(self, definition):
        output = parse_fr_definition(definition)
        assert output.mood is not None
        assert output.tense is not None
        assert output.person is not None
        assert output.lemma is not None

    @parameterized.expand([f for f in fr_verb_forms if 'Troisième personne' in f])
    def test_parse_fr_definition_check_person(self, definition):
        output = parse_fr_definition(definition)
        self.assertEqual(output.person, 'third-person')

    @parameterized.expand([f for f in fr_verb_forms if 'subjonctif' in f])
    def test_parse_fr_definition_check_mood(self, definition):
        output = parse_fr_definition(definition)
        self.assertEqual(output.mood, 'subjunctive')

    @parameterized.expand([f for f in fr_verb_forms if 'fermer' in f])
    def test_parse_fr_definition_check_lemma(self, definition):
        output = parse_fr_definition(definition)
        self.assertEqual(output.lemma, 'fermer')

    @parameterized.expand([f for f in fr_verb_forms if 'acentuar' in f])
    def test_parse_fr_definition_check_lemma_2(self, definition):
        output = parse_fr_definition(definition)
        self.assertEqual(output.lemma, 'acentuar')

    @parameterized.expand([f for f in fr_verb_forms if 'singulier' in f])
    def test_parse_fr_definition_check_number(self, definition):
        output = parse_fr_definition(definition)
        self.assertEqual(output.number, 'singular')


class TestVerbFormParsersTemplate(TestCase):
    fi_verb_forms = [
        '{{fi-verb form of|pn=1p|tm=cond|absorboitua}}',
        '{{fi-verb form of|pn=pass|tm=pres|c=1|absorboitua}}',
        '{{fi-verb form of|pn=pass|tm=potn|c=1|aavikoitua}}',
        '{{fi-verb form of|tm=pres|c=1|absorboitua}}',
        '{{fi-verb form of|pn=1s|tm=impr|absorboitua}',
        '{{fi-verb form of|pn=2s|tm=impr|c=1|absorboitu}}',
        '{{fi-verb form of|pn=3s|tm=pres|absorboitua}}',
        '{{fi-verb form of|pn=1p|tm=past|absorboitua}',
        '{{fi-verb form of|pn=2p|tm=pres|c=1|absorboitu}}',
        '{{fi-verb form of|pn=3p|tm=potn|absorboitua}}'
    ]

    def test_parse_verb_form_inflection_of(self):
        template_expression = '{{inflection of|finalizzare||3|p|cond|lang=it}}'
        output = parse_verb_form_inflection_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.number, 'p')
        self.assertEqual(output.lemma, 'finalizzare')
        self.assertEqual(output.mood, 'cond')
        self.assertEqual(output.person, '3')

    def test_parse_inflection_of_noun_form_2(self):
        template_expression = '{{inflection of|fr|sursaturer||3|s|simple|futr}}'
        output = parse_verb_form_inflection_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.lemma, 'sursaturer')
        self.assertEqual(output.number, 's')

    def test_parse_ca_verb_form_of(self):
        template_expression = '{{ca-verb form of|p=2|n=sg|t=impf|m=ind|abordar}}'
        output = parse_ca_verb_form_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.number, 'sg')
        self.assertEqual(output.lemma, 'abordar')
        self.assertEqual(output.tense, 'impf')
        self.assertEqual(output.mood, 'ind')
        self.assertEqual(output.person, '2')

    def test_parse_es_compound_of(self):
        template_expression = '{{es-compound of|tipific|ar|tipificando|se|mood=part}}'
        output = parse_es_compound_of(template_expression)
        self.assertEqual(output.mood, 'part')

    def test_parse_es_verb_form_of(self):
        template_expression = '{{es-verb form of|person=third-person|number=plural|tense=imperfect|mood=subjunctive|sera=ra|ending=ar|terminar}}'
        output = parse_es_verb_form_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.number, 'plural')
        self.assertEqual(output.lemma, 'terminar')
        self.assertEqual(output.tense, 'imperfect')
        self.assertEqual(output.mood, 'subjunctive')
        self.assertEqual(output.person, 'third-person')

        template_expression = '{{es-verb form of|ending=ar|mood=indicative|tense=preterite|pers=1|number=singular|despegar}}'
        output = parse_es_verb_form_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.lemma, 'despegar')
        self.assertEqual(output.number, 'singular')
        self.assertEqual(output.tense, 'preterite')
        self.assertEqual(output.mood, 'indicative')
        self.assertEqual(output.person, '1')

        # edge cases (5% of entries)
        template_expression = '{{es-verb form of|ending=ar|mood=indicative|tense=future|pers=2|formal=no|number=plural|ababillarse|region=Spain}}'
        output = parse_es_verb_form_of(template_expression)
        self.assertEqual(output.lemma, 'ababillarse')
        self.assertEqual(output.number, 'plural')
        self.assertEqual(output.tense, 'future')
        self.assertEqual(output.mood, 'indicative')
        self.assertEqual(output.person, '2')

    def test_parse_fi_verb_form_of(self):
        template_expression = '{{fi-verb form of|pn=pass|tm=impr|absorboitua}}'
        output = parse_fi_verb_form_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.number, 's')
        self.assertEqual(output.tense, 'pres')
        self.assertEqual(output.lemma, 'absorboitua')

    @parameterized.expand(fi_verb_forms)
    def test_parse_fi_verb_form_of_2(self, template_expression):
        output = parse_fi_verb_form_of(template_expression)

    def test_parse_fi_form_of(self):
        template_expression = '{{fi-form of|aateloida|pr=third-person|pl=singular|mood=indicative|tense=present}}'
        output = parse_fi_form_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.person, 'third-person')
        self.assertEqual(output.number, 'singular')
        self.assertEqual(output.tense, 'present')
        self.assertEqual(output.mood, 'indicative')
        self.assertEqual(output.lemma, 'aateloida')

    def test_parse_de_verb_form_of(self):
        for mood in ['k1', 'k2']:
            for tense_name, tense_param in [('pres', 'g'), ('pret', 'v')]:
                template_expression = '{{de-verb form of|abfangen|1|%s|s|%s|a}}' % (tense_param, mood)
                output = parse_de_verb_form_of(template_expression)
                self.assertIsInstance(output, VerbForm)
                self.assertEqual(output.person, '1')
                self.assertEqual(output.number, 's')
                self.assertEqual(output.tense, tense_name)
                self.assertEqual(output.mood, 'subj')
                self.assertEqual(output.lemma, 'abfangen')

    def test_parse_la_verb_form_inflection_of(self):
        template_expression = '{{inflection of|la|abaestuō||2|p|impf|actv|indc}}'
        output = parse_la_verb_form_inflection_of(template_expression)
        self.assertEqual(output.person, '2')
        self.assertEqual(output.number, 'p')
        self.assertEqual(output.tense, 'impf')
        self.assertEqual(output.lemma, 'abaestuō')
        self.assertEqual(output.mood, 'indc')
