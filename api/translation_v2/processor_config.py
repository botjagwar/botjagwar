"""Utilities for loading pre/post processing configuration."""

from __future__ import annotations

import configparser
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from api.config import CONF_ROOT_PATH
from api.model.word import Entry

log = logging.getLogger(__name__)


class ProcessorConfigurationError(Exception):
    """Raised when a processor configuration entry is invalid."""


class ProcessorType:
    """Supported processor stages."""

    BEFORE_TRANSLATION = "before_translation"
    AFTER_TRANSLATION = "after_translation"

    @classmethod
    def values(cls) -> Tuple[str, str]:
        """Return all accepted processor type values."""

        return cls.BEFORE_TRANSLATION, cls.AFTER_TRANSLATION


def _parse_language_list(value: Optional[str]) -> Optional[List[str]]:
    """Parse a comma separated list of languages into a list."""

    if not value:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


@dataclass
class ProcessorDefinition:
    """Single processor definition parsed from the configuration file."""

    language: str
    part_of_speech: str
    function_name: str
    processor_type: str
    order: int = 0
    exclude_languages: Optional[List[str]] = None
    only_languages: Optional[List[str]] = None
    arguments: List[str] = field(default_factory=list)

    def matches(self, language: str, part_of_speech: Optional[str]) -> bool:
        """Return True if the definition applies to the provided entry."""

        language = language or ""
        part_of_speech = part_of_speech or ""

        if self.language != "*" and self.language != language:
            return False

        if self.part_of_speech != "*" and self.part_of_speech != part_of_speech:
            return False

        if self.only_languages and language not in self.only_languages:
            return False

        if self.exclude_languages and language in self.exclude_languages:
            return False

        return True

    def resolve_arguments(self, entry: Entry) -> Tuple[str, ...]:
        """Resolve templated arguments for the provided entry."""

        resolved: List[str] = []
        for value in self.arguments:
            resolved.append(_substitute_placeholders(value, entry))
        return tuple(resolved)


def _substitute_placeholders(value: str, entry: Entry) -> str:
    """Replace ``{{attribute}}`` placeholders using the entry attributes."""

    def replacement(match: re.Match[str]) -> str:
        attribute_name = match.group(1)
        if not hasattr(entry, attribute_name):
            raise ProcessorConfigurationError(
                f"Entry has no attribute '{attribute_name}' for placeholder substitution"
            )
        attribute_value = getattr(entry, attribute_name)
        return "" if attribute_value is None else str(attribute_value)

    return re.sub(r"\{\{([^}]+)\}\}", replacement, value)


class ProcessorConfigManager:
    """Load processor definitions from ``processors.ini``."""

    CONFIG_PATH = os.path.join(CONF_ROOT_PATH, "entry_translator", "processors.ini")

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self.CONFIG_PATH
        self._definitions: List[ProcessorDefinition] = []
        self._load_config()

    def _load_config(self) -> None:
        """Load and parse the processor configuration file."""

        if not os.path.exists(self.config_path):
            log.debug("Processor configuration '%s' not found.", self.config_path)
            self._definitions = []
            return

        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str  # Preserve the case of keys

        parser.read(self.config_path)

        definitions: List[ProcessorDefinition] = []

        for section in parser.sections():
            try:
                definition = self._parse_section(section, parser.items(section))
            except ProcessorConfigurationError as exc:
                log.error("Invalid processor configuration in section '%s': %s", section, exc)
                raise
            definitions.append(definition)

        definitions.sort(key=lambda definition: definition.order)
        self._definitions = definitions

    def _parse_section(
        self, section_name: str, items: Sequence[Tuple[str, str]]
    ) -> ProcessorDefinition:
        """Parse a configuration section into a :class:`ProcessorDefinition`."""

        try:
            language, part_of_speech, function_name = (
                part.strip() for part in section_name.split(":", maxsplit=2)
            )
        except ValueError as exc:
            raise ProcessorConfigurationError(
                "Section name must be formatted as '<language>:<part_of_speech>:<function>'"
            ) from exc

        options = {name: value for name, value in items}

        processor_type = options.get("type", ProcessorType.AFTER_TRANSLATION)
        if processor_type not in ProcessorType.values():
            raise ProcessorConfigurationError(
                f"Unsupported processor type '{processor_type}'"
            )

        order = int(options.get("order", "0"))
        exclude_languages = _parse_language_list(options.get("exclude_languages"))
        only_languages = _parse_language_list(
            options.get("only_languages") or options.get("only_on_languages")
        )

        if language != "*" and (exclude_languages or only_languages):
            raise ProcessorConfigurationError(
                "'exclude_languages' and 'only_languages' are only allowed for wildcard language sections"
            )

        arguments: List[str] = []
        for key, value in items:
            if key.startswith("arguments__"):
                arguments.append(value)

        return ProcessorDefinition(
            language=language,
            part_of_speech=part_of_speech,
            function_name=function_name,
            processor_type=processor_type,
            order=order,
            exclude_languages=exclude_languages,
            only_languages=only_languages,
            arguments=arguments,
        )

    def get_definitions(
        self, language: str, part_of_speech: Optional[str], processor_type: str
    ) -> List[ProcessorDefinition]:
        """Return all matching processor definitions for the provided entry."""

        return [
            definition
            for definition in self._definitions
            if definition.processor_type == processor_type
            and definition.matches(language, part_of_speech)
        ]

    def instantiate_processor(
        self, definition: ProcessorDefinition, entry: Entry, modules: Iterable[object]
    ) -> Tuple[Callable[[List[Entry]], List[Entry]], Tuple[str, ...]]:
        """Instantiate a processor callable."""

        resolved_arguments = definition.resolve_arguments(entry)

        for module in modules:
            if hasattr(module, definition.function_name):
                factory = getattr(module, definition.function_name)
                return factory(*resolved_arguments), resolved_arguments

        raise ProcessorConfigurationError(
            f"Processor function '{definition.function_name}' is not available"
        )
