import types

import pytest

from api.model.word import Entry
from api.translation_v2.processor_config import (
    ProcessorConfigManager,
    ProcessorConfigurationError,
    ProcessorType,
)


@pytest.fixture
def entry():
    return Entry(entry="test", part_of_speech="ana", definitions=["def"], language="en")


def write_config(tmp_path, content: str):
    config_path = tmp_path / "processors.ini"
    config_path.write_text(content)
    return config_path


def test_definitions_sorted_by_order(tmp_path):
    config_path = write_config(
        tmp_path,
        """
        [*:ana:first]
        type=after_translation
        order=200
        arguments__arg1=foo

        [*:ana:second]
        type=after_translation
        order=100
        arguments__arg1=bar
        """,
    )

    manager = ProcessorConfigManager(config_path=str(config_path))
    definitions = manager.get_definitions("en", "ana", ProcessorType.AFTER_TRANSLATION)

    assert [definition.function_name for definition in definitions] == ["second", "first"]


def test_invalid_language_filters(tmp_path):
    config_path = write_config(
        tmp_path,
        """
        [fr:ana:func]
        type=after_translation
        exclude_languages=mg
        """,
    )

    with pytest.raises(ProcessorConfigurationError):
        ProcessorConfigManager(config_path=str(config_path))


def test_instantiate_with_placeholders(tmp_path, entry):
    config_path = write_config(
        tmp_path,
        """
        [*:ana:dummy]
        type=after_translation
        order=1
        arguments__arg1={{language}}
        """,
    )

    manager = ProcessorConfigManager(config_path=str(config_path))
    definition = manager.get_definitions("en", "ana", ProcessorType.AFTER_TRANSLATION)[0]

    module = types.SimpleNamespace(dummy=lambda value: (lambda entries: entries))
    callable_, resolved = manager.instantiate_processor(definition, entry, [module])

    assert resolved == ("en",)
    assert callable_([entry]) == [entry]


def test_missing_placeholder_attribute(tmp_path, entry):
    config_path = write_config(
        tmp_path,
        """
        [*:ana:dummy]
        type=after_translation
        order=1
        arguments__arg1={{unknown}}
        """,
    )

    manager = ProcessorConfigManager(config_path=str(config_path))
    definition = manager.get_definitions("en", "ana", ProcessorType.AFTER_TRANSLATION)[0]

    module = types.SimpleNamespace(dummy=lambda value: (lambda entries: entries))
    with pytest.raises(ProcessorConfigurationError):
        manager.instantiate_processor(definition, entry, [module])
