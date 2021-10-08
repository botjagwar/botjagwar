from unittest import TestCase

from api.parsers.constants.en import MOOD, TENSE, NUMBER, PERSONS, VOICE, CASES, GENDER
from api.parsers.inflection_template import NounForm, VerbForm, AdjectiveForm


class TestInflectionTemplateClassesEnglish(TestCase):
    def test_NounForm(self):
        obj = NounForm('slk', 'acc', 'p', 'f')
        mg_def = obj.to_definition('en')
        self.assertIn(CASES['acc'], mg_def)
        self.assertIn(NUMBER['p'], mg_def)
        self.assertIn(GENDER['f'], mg_def)

    def test_VerbForm(self):
        obj = VerbForm('alsk', 'pres', 'cond', '1', 'p', voice='pass')
        mg_def = obj.to_definition('en')
        self.assertIn(MOOD['cond'], mg_def)
        self.assertIn(PERSONS['1'], mg_def)
        self.assertIn(NUMBER['p'], mg_def)
        self.assertIn(VOICE['pass'], mg_def)
        self.assertIn(TENSE['pres'], mg_def)

    def test_AdjectiveForm(self):
        obj = AdjectiveForm('qpowi', 'acc', 's', 'm')
        mg_def = obj.to_definition('en')
        self.assertIn(CASES['acc'], mg_def)
        self.assertIn(NUMBER['s'], mg_def)
        self.assertIn(GENDER['m'], mg_def)

