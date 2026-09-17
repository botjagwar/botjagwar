from typing import Callable, Dict, Tuple, Union

import mwparserfromhell
from mwparserfromhell.wikicode import Wikicode

from api.parsers.models.inflection import NonLemma, ParserError, ParserNotFoundError


DefinitionSource = Union[str, Wikicode]


class WiktionaryDefinitionParser(object):
    """Parse definition lines using :mod:`mwparserfromhell`."""

    def __init__(self, wiki_language: str = "en"):
        self.process_function: Dict[
            Tuple[type, str], Callable[[DefinitionSource], NonLemma]
        ] = {}
        self.wiki_language = wiki_language

    def add_parser(
        self,
        return_class: type,
        parser_function: Callable[[DefinitionSource], NonLemma],
    ) -> None:
        if (return_class, self.wiki_language) in self.process_function:
            raise ParserError(
                f"parser already exists for '{return_class.__class__.__name__}'"
            )
        self.process_function[(return_class, self.wiki_language)] = parser_function

    def get_elements(
        self, expected_class: type, form_of_definition: DefinitionSource
    ) -> NonLemma:
        process_key = (expected_class, self.wiki_language)
        if process_key not in self.process_function:
            raise ParserNotFoundError(
                f"No parser defined for class {expected_class.__name__} and "
                f"language '{self.wiki_language}': {form_of_definition!r}"
            )

        process_function = self.process_function[process_key]
        wikicode = (
            form_of_definition
            if isinstance(form_of_definition, Wikicode)
            else mwparserfromhell.parse(form_of_definition)
        )

        try:
            result = process_function(wikicode)
        except ValueError as exc:
            print("ERROR: ", exc)
            raise

        if not isinstance(result, expected_class):
            raise ParserError(
                "Wrong object returned. Expected "
                f"{expected_class.__name__}, got {result.__class__.__name__}"
            )
        return result

    def get_lemma(self, expected_class: type, template_expression: DefinitionSource) -> str:
        return self.get_elements(expected_class, template_expression).lemma
