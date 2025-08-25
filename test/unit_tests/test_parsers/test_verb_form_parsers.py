from unittest import TestCase

from parameterized import parameterized

from api.model.word import Entry

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

    @parameterized.expand([f for f in fr_verb_forms if "Troisième personne" in f])
    def test_parse_fr_definition_check_person(self, definition):
        output = parse_fr_definition(definition)
        self.assertEqual(output.person, "third-person")

    @parameterized.expand([f for f in fr_verb_forms if "subjonctif" in f])
    def test_parse_fr_definition_check_mood(self, definition):
        output = parse_fr_definition(definition)
        self.assertEqual(output.mood, "subjunctive")

    @parameterized.expand([f for f in fr_verb_forms if "fermer" in f])
    def test_parse_fr_definition_check_lemma(self, definition):
        output = parse_fr_definition(definition)
        self.assertEqual(output.lemma, "fermer")

    @parameterized.expand([f for f in fr_verb_forms if "acentuar" in f])
    def test_parse_fr_definition_check_lemma_2(self, definition):
        output = parse_fr_definition(definition)
        self.assertEqual(output.lemma, "acentuar")

    @parameterized.expand([f for f in fr_verb_forms if "singulier" in f])
    def test_parse_fr_definition_check_number(self, definition):
        output = parse_fr_definition(definition)
        self.assertEqual(output.number, "singular")


class TestVerbFormParsersTemplate(TestCase):
    fi_verb_forms = [
        "{{fi-verb form of|pn=1p|tm=cond|absorboitua}}",
        "{{fi-verb form of|pn=pass|tm=pres|c=1|absorboitua}}",
        "{{fi-verb form of|pn=pass|tm=potn|c=1|aavikoitua}}",
        "{{fi-verb form of|tm=pres|c=1|absorboitua}}",
        "{{fi-verb form of|pn=1s|tm=impr|absorboitua}",
        "{{fi-verb form of|pn=2s|tm=impr|c=1|absorboitu}}",
        "{{fi-verb form of|pn=3s|tm=pres|absorboitua}}",
        "{{fi-verb form of|pn=1p|tm=past|absorboitua}",
        "{{fi-verb form of|pn=2p|tm=pres|c=1|absorboitu}}",
        "{{fi-verb form of|pn=3p|tm=potn|absorboitua}}",
    ]

    def test_parse_verb_form_inflection_of(self):
        template_expression = "{{inflection of|finalizzare||3|p|cond|lang=it}}"
        output = parse_verb_form_inflection_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.number, "p")
        self.assertEqual(output.lemma, "finalizzare")
        self.assertEqual(output.mood, "cond")
        self.assertEqual(output.person, "3")

    def test_parse_inflection_of_noun_form_2(self):
        template_expression = "{{inflection of|fr|sursaturer||3|s|simple|futr}}"
        output = parse_verb_form_inflection_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.lemma, "sursaturer")
        self.assertEqual(output.number, "s")

    def test_parse_inflection_of_noun_form_3(self):
        template_expression = '{{inflection of|ast|fumar||1|s|impf|indc}}'
        output = parse_verb_form_inflection_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.lemma, "fumar")
        self.assertEqual(output.number, "s")
        self.assertEqual(output.person, "1")
        self.assertEqual(output.mood, "indc")

    def test_parse_ca_verb_form_of(self):
        template_expression = "{{ca-verb form of|p=2|n=sg|t=impf|m=ind|abordar}}"
        output = parse_ca_verb_form_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.number, "sg")
        self.assertEqual(output.lemma, "abordar")
        self.assertEqual(output.tense, "impf")
        self.assertEqual(output.mood, "ind")
        self.assertEqual(output.person, "2")

    def test_parse_es_compound_of(self):
        template_expression = "{{es-compound of|tipific|ar|tipificando|se|mood=part}}"
        output = parse_es_compound_of(template_expression)
        self.assertEqual(output.mood, "part")

    def test_parse_fi_verb_form_of(self):
        template_expression = "{{fi-verb form of|pn=pass|tm=impr|absorboitua}}"
        output = parse_fi_verb_form_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.number, "s")
        self.assertEqual(output.tense, "pres")
        self.assertEqual(output.lemma, "absorboitua")

    @parameterized.expand(fi_verb_forms)
    def test_parse_fi_verb_form_of_2(self, template_expression):
        output = parse_fi_verb_form_of(template_expression)

    def test_parse_fi_form_of(self):
        template_expression = "{{fi-form of|aateloida|pr=third-person|pl=singular|mood=indicative|tense=present}}"
        output = parse_fi_form_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.person, "third-person")
        self.assertEqual(output.number, "singular")
        self.assertEqual(output.tense, "present")
        self.assertEqual(output.mood, "indicative")
        self.assertEqual(output.lemma, "aateloida")

    def test_parse_de_verb_form_of(self):
        for mood in ["k1", "k2"]:
            for tense_name, tense_param in [("pres", "g"), ("pret", "v")]:
                template_expression = "{{de-verb form of|abfangen|1|%s|s|%s|a}}" % (
                    tense_param,
                    mood,
                )
                output = parse_de_verb_form_of(template_expression)
                self.assertIsInstance(output, VerbForm)
                self.assertEqual(output.person, "1")
                self.assertEqual(output.number, "s")
                self.assertEqual(output.tense, tense_name)
                self.assertEqual(output.mood, "subj")
                self.assertEqual(output.lemma, "abfangen")

    def test_parse_la_verb_form_inflection_of(self):
        template_expression = "{{inflection of|la|abaestuō||2|p|impf|actv|indc}}"
        output = parse_la_verb_form_inflection_of(template_expression)
        self.assertEqual(output.person, "2")
        self.assertEqual(output.number, "p")
        self.assertEqual(output.tense, "impf")
        self.assertEqual(output.lemma, "abaestuō")
        self.assertEqual(output.mood, "indc")

    def test_es_verb_form_parser_regular(self):
        from api.parsers.functions.verb_forms.es import (
            MOOD_TENSES,
            ENDINGS,
            IMPERATIVE_ENDINGS,
            IMPERATIVE_PRONOUNS,
            IMPERATIVE_PERSON_NUMBER,
            _PERSONS,
            _NUMBERS,
            _regular_gerund,
            _regular_participle,
        )

        lemma = "hablar"
        conj = lemma[-2:]
        stem = lemma[:-2]

        finite_forms = set()
        for mood, tenses in MOOD_TENSES.items():
            for tense in tenses:
                endings = ENDINGS[(mood, tense, conj)]
                base = lemma if tense in {"future", "conditional"} else stem
                seen = set()
                for idx, ending in enumerate(endings):
                    word = base + ending
                    if word in seen or word in finite_forms:
                        continue
                    seen.add(word)
                    finite_forms.add(word)
                    context = {"entry": Entry(entry=word, language='es', part_of_speech='mat',
                                              definitions=[f"{{es-verb form of|{lemma}}}"])}
                    vf = parse_es_verb_form_of(f"{{es-verb form of|{lemma}}}", **context)

                    # For commented code below: Tests checks, but assertion fails. No idea why.
                    # self.assertEqual((vf.mood, vf.tense), (mood, tense))
                    assert (vf.mood, vf.tense) == (mood,
                                                   tense), f"Failed for word: {word}, expected ({mood}, {tense}), got ({vf.mood}, {vf.tense})"
                    if vf.person is not None:
                        self.assertEqual((vf.person, vf.number), (_PERSONS[idx], _NUMBERS[idx]))

        endings = IMPERATIVE_ENDINGS[conj]
        for pronoun, ending in zip(IMPERATIVE_PRONOUNS, endings):
            word = stem + ending
            if word in finite_forms:
                continue
            context = {"entry": Entry(entry=word, language='es', part_of_speech='mat',
                                      definitions=[f"{{es-verb form of|{lemma}}}"])}
            vf = parse_es_verb_form_of(f"{{es-verb form of|{lemma}}}", **context)
            self.assertEqual((vf.mood, vf.tense), ("imperative", "affirmative"))
            self.assertEqual((vf.person, vf.number), IMPERATIVE_PERSON_NUMBER[pronoun])

        gerund = _regular_gerund(lemma)
        context = {"entry": Entry(
            entry=gerund, language='es', part_of_speech='mat',
            definitions=[f"{{es-verb form of|{lemma}}}"])
        }
        vf = parse_es_verb_form_of(f"{{es-verb form of|{lemma}}}", **context)
        self.assertEqual(vf.mood, "gerund")

        participle = _regular_participle(lemma)
        context = {"entry": Entry(
            entry=participle, language='es', part_of_speech='mat',
            definitions=[f"{{es-verb form of|{lemma}}}"])
        }
        vf = parse_es_verb_form_of(f"{{es-verb form of|{lemma}}}", **context)
        assert (vf.mood, vf.tense) == ("participle", "past")

    def test_es_verb_form_parser_irregular(self):
        from api.parsers.functions.verb_forms.es import (
            MOOD_TENSES,
            IRREGULAR_FORMS,
            IMPERATIVE_PRONOUNS,
            IMPERATIVE_PERSON_NUMBER,
            IRREGULAR_GERUNDS,
            IRREGULAR_PARTICIPLES,
            _PERSONS,
            _NUMBERS,
        )

        lemma = "ser"
        forms = IRREGULAR_FORMS[lemma]

        finite_forms = set()
        for mood, tenses in MOOD_TENSES.items():
            for tense in tenses:
                if (mood, tense) not in forms:
                    continue
                seen = set()
                for idx, word in enumerate(forms[(mood, tense)]):
                    if word in seen or word in finite_forms:
                        continue
                    seen.add(word)
                    finite_forms.add(word)
                    context = {"entry": Entry(entry=word, language='es', part_of_speech='mat',
                                              definitions=[f"{{es-verb form of|{lemma}}}"])}
                    vf = parse_es_verb_form_of(f"{{es-verb form of|{lemma}}}", **context)
                    assert (vf.mood, vf.tense) == (mood, tense)
                    if vf.person is not None:
                        assert (vf.person, vf.number) == (_PERSONS[idx], _NUMBERS[idx])

        imp_forms = forms[("imperative", "affirmative")]
        for pronoun, word in zip(IMPERATIVE_PRONOUNS, imp_forms):
            if word in finite_forms:
                continue

            context = {"entry": Entry(
                entry=word, language='es', part_of_speech='mat',
                definitions=[f"{{es-verb form of|{lemma}}}"])
            }
            vf = parse_es_verb_form_of(f"{{es-verb form of|{lemma}}}", **context)
            self.assertEqual((vf.mood, vf.tense), ("imperative", "affirmative"))
            self.assertEqual((vf.person, vf.number), IMPERATIVE_PERSON_NUMBER[pronoun])

        gerund = IRREGULAR_GERUNDS[lemma]
        context = {"entry": Entry(
            entry=gerund, language='es', part_of_speech='mat',
            definitions=[f"{{es-verb form of|{lemma}}}"])
        }
        vf = parse_es_verb_form_of(f"{{es-verb form of|{lemma}}}", **context)
        self.assertEqual(vf.mood, "gerund")

        participle = IRREGULAR_PARTICIPLES[lemma]
        context = {"entry": Entry(
            entry=participle, language='es', part_of_speech='mat',
            definitions=[f"{{es-verb form of|{lemma}}}"])
        }
        vf = parse_es_verb_form_of(f"{{es-verb form of|{lemma}}}", **context)
        self.assertEqual((vf.mood, vf.tense), ("participle", "past"))

    def test_es_gerund_with_clitic_pronouns(self):
        cases = [
            ("hablándome", "hablar"),
            ("bañándose", "bañarse"),
            ("dándomelo", "dar"),
        ]
        for word, lemma in cases:
            context = {
                "entry": Entry(
                    entry=word,
                    language="es",
                    part_of_speech="mat",
                    definitions=[f"{{es-verb form of|{lemma}}}"],
                )
            }
            vf = parse_es_verb_form_of(f"{{es-verb form of|{lemma}}}", **context)
            self.assertEqual(vf.mood, "gerund")
            self.assertEqual(vf.lemma, lemma)
