# coding: utf8

from api.parsers.models.inflection import (
    VerbForm,
    AdjectiveForm,
    NounForm,
    NonLemma,
    ParserError,
    ParserNotFoundError,
)


class WiktionaryInflectionTemplateParser(object):
    def __init__(self):
        self.process_function = {}

    def add_parser(self, return_class, template_name, parser_function):
        if (return_class, template_name) in self.process_function:
            raise ParserError(
                f"parser already exists for '{return_class}', '{template_name}' "
            )
        self.process_function[(return_class, template_name)] = parser_function

    def get_elements(self, expected_class, form_of_definition, **context) -> [NonLemma]:
        # fixme: detect several templates on the same line, and raise exception if such case is encountered.
        # current way of parsing template expressions fails spectacularly (InvalidTitle exceptions) in nasty cases:
        # e.g. {{es-verb form of|mood=imp|num=s|pers=2|formal=n|sense=+|ending=ir|venir}} + {{m|es|te||}}.
        # (true story)
        orig_template_expression = form_of_definition
        for c in "{}":
            form_of_definition = form_of_definition.replace(c, "")
        parts = form_of_definition.split("|")
        if (expected_class, parts[0]) not in list(self.process_function.keys()):
            raise ParserNotFoundError(
                f'No parser defined for "{parts[0]}": {orig_template_expression}'
            )
        try:
            ret = self.process_function[(expected_class, parts[0])](
                form_of_definition, **context
            )
            if not isinstance(ret, expected_class):
                raise ParserError(
                    f"Wrong object returned. Expected {expected_class.__name__}, got {ret.__class__.__name__}"
                )
            return ret
        except ValueError as exc:
            print("ERROR: ", exc)
            raise exc

    def get_lemma(self, expected_class, template_expression) -> str:
        return self.get_elements(expected_class, template_expression).lemma
