from api.parsers.models.inflection import (
    VerbForm,
    AdjectiveForm,
    NounForm,
    NonLemma,
    ParserError,
    ParserNotFoundError,
)


class WiktionaryDefinitionParser(object):
    def __init__(self):
        self.process_function = {}

    def add_parser(self, return_class, parser_function):
        if return_class in self.process_function:
            raise ParserError(
                f"parser already exists for '{return_class.__class__.__name__}'"
            )
        self.process_function[return_class] = parser_function

    def get_elements(
        self, expected_class, form_of_definition
    ) -> ["VerbForm", "AdjectiveForm", "NounForm", "NonLemma"]:
        orig_template_expression = form_of_definition
        for c in "{}":
            form_of_definition = form_of_definition.replace(c, "")
        parts = form_of_definition.split("|")
        if expected_class not in list(self.process_function.keys()):
            raise ParserNotFoundError(
                f'No parser defined for "{parts[0]}": {orig_template_expression}'
            )
        try:
            ret = self.process_function[expected_class](form_of_definition)
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
