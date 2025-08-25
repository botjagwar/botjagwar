from api.parsers.definition import WiktionaryDefinitionParser
from api.parsers.functions.noun_forms.definitions import (
    parameterized_parse_fr_definition,
)
from api.parsers.functions.verb_forms.definitions import parse_fr_definition
from api.parsers.models.inflection import (
    NounForm,
    VerbForm,
    AdjectiveForm,
    Romanization,
)
from .inflection_template import WiktionaryInflectionTemplateParser

TEMPLATE_TO_OBJECT = {
    "e-ana": NounForm,
    "ana-pr": NounForm,
    "e-mpam-ana": AdjectiveForm,
    "e-mat": VerbForm,
    "ova-mat": VerbForm,
    "ana": NounForm,
    "mpam-ana": AdjectiveForm,
    "mpam": AdjectiveForm,
    "mat": VerbForm,
    "rômanizasiona": Romanization,
}

FORM_OF_TEMPLATE = {
    "ana": "e-ana",
    "rômanizasiona": "rômanizasiona",
    "mpam-ana": "e-mpam-ana",
    "mpam": "e-mpam-ana",
    "mat": "e-mat",
}

fr_definitions_parser = WiktionaryDefinitionParser(wiki_language='fr')
templates_parser = WiktionaryInflectionTemplateParser()

fr_definitions_parser.add_parser(NounForm, parameterized_parse_fr_definition(NounForm))
fr_definitions_parser.add_parser(AdjectiveForm, parameterized_parse_fr_definition(AdjectiveForm))

fr_definitions_parser.add_parser(VerbForm, parse_fr_definition)


def get_lemma(expected_class, template_expression):
    return templates_parser.get_lemma(expected_class, template_expression)
