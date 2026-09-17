
import pytest
from api.entryprocessor.wiki.fr import FRWiktionaryProcessor
from api.entryprocessor.wiki.fr import DefinitionProcessingConfig



@pytest.fixture
def processor():
    return FRWiktionaryProcessor(test=True)


def test_get_all_entries_empty_content(mocker):
    """Test get_all_entries when content is empty."""
    processor = FRWiktionaryProcessor()
    processor.content = ""

    mock_parse_language_sections = mocker.patch.object(
        processor, "_parse_language_sections", return_value=[]
    )

    result = processor.get_all_entries()

    assert result == []
    mock_parse_language_sections.assert_not_called()


def test_get_all_entries_with_content_no_additional_data(mocker):
    """Test get_all_entries with valid content and no additional data."""
    processor = FRWiktionaryProcessor()
    processor.content = "Language section content"
    mock_re = mocker.patch("api.entryprocessor.wiki.fr.re.findall", return_value=["section1", "section2"])

    mock_parse_language_sections = mocker.patch.object(
        processor, "_parse_language_sections", return_value=["entry1", "entry2"]
    )

    result = processor.get_all_entries()

    assert result == ["entry1", "entry2", "entry1", "entry2"]
    mock_re.assert_called_once()
    mock_parse_language_sections.assert_any_call("section1", False)
    mock_parse_language_sections.assert_any_call("section2", False)


def test_get_all_entries_with_content_and_additional_data(mocker):
    """Test get_all_entries with valid content and additional data."""
    processor = FRWiktionaryProcessor()
    processor.content = "Language section content"
    mock_re = mocker.patch("api.entryprocessor.wiki.fr.re.findall", return_value=["section1", "section2"])

    mock_parse_language_sections = mocker.patch.object(
        processor, "_parse_language_sections", return_value=["entry1", "entry2"]
    )

    result = processor.get_all_entries(get_additional_data=True)

    assert result == ["entry1", "entry2", "entry1", "entry2"]
    mock_re.assert_called_once()
    mock_parse_language_sections.assert_any_call("section1", True)
    mock_parse_language_sections.assert_any_call("section2", True)


def test_parse_language_sections_no_additional_data(processor, mocker):
    # Mock dependencies
    mocker.patch.object(processor, '_parse_section_content', return_value=({"key": "value"}, ["example"]))
    mocker.patch.object(processor, '_create_entries_from_definitions', return_value=["entry1", "entry2"])

    language_section = ["en"]
    processor.content = "== {{langue|en}} ==\n== {{langue|fr}} =="

    result = processor._parse_language_sections(language_section, get_additional_data=False)

    assert result == ["entry1", "entry2"]
    processor._parse_section_content.assert_called_once()
    processor._create_entries_from_definitions.assert_called_once_with({"key": "value"}, "en", None, False)


def test_parse_language_sections_no_section_content(processor, mocker):
    # Mock dependencies
    mocker.patch.object(processor, '_parse_section_content', return_value=({}, []))
    mocker.patch.object(processor, '_create_entries_from_definitions', return_value=[])

    language_section = ["es"]
    processor.content = "== {{langue|en}} ==\n== {{langue|fr}} =="

    result = processor._parse_language_sections(language_section, get_additional_data=False)

    assert result == []
    processor._parse_section_content.assert_called_once()
    processor._create_entries_from_definitions.assert_called_once_with({}, "es", None, False)


def test_parse_section_content_with_definitions():
    processor = FRWiktionaryProcessor()
    lines = [
        "== {{langue|fr}} ==",
        "=== {{S|nom|fr}} ===",
        "# Un morceau de matériel.",
        "# Un petit objet utilisé pour l'attache.",
        "#* Exemple de phrase pour l'attache.",
    ]
    definitions, examples = processor._parse_section_content(lines)

    assert "ana" in definitions
    assert definitions['ana'] == ["Un morceau de matériel.", "Un petit objet utilisé pour l'attache."]
    assert "Un petit objet utilisé pour l'attache." in examples
    assert examples["Un petit objet utilisé pour l'attache."] == ["Exemple de phrase pour l'attache."]


def test_parse_section_content_with_empty_lines():
    processor = FRWiktionaryProcessor()
    lines = []
    definitions, examples = processor._parse_section_content(lines)

    assert definitions == {}
    assert examples == {}


def test_parse_section_content_with_multiple_pos():
    processor = FRWiktionaryProcessor()
    lines = [
        "== {{langue|fr}} ==",
        "=== {{S|nom|fr}} ===",
        "# Un morceau de matériel.",
        "=== {{S|adjectif|fr}} ===",
        "# Décrivant le matériel.",
    ]
    definitions, examples = processor._parse_section_content(lines)

    # assert "ana" in definitions
    # assert definitions["ana"] == ["Un morceau de matériel."]
    assert "mpam" in definitions
    assert definitions["mpam"] == ["Décrivant le matériel."]


def test_parse_section_content_with_nom_de_famille():
    """Map 'nom de famille' sections to ana-pr instead of crashing."""
    processor = FRWiktionaryProcessor()
    lines = [
        "== {{langue|fr}} ==",
        "=== {{S|nom de famille|fr}} ===",
        "# Un nom de famille français.",
    ]
    definitions, examples = processor._parse_section_content(lines)

    assert "ana-pr" in definitions
    assert definitions["ana-pr"] == ["Un nom de famille français."]


def test_parse_section_content_with_unknown_pos_no_crash():
    """Skip unknown part of speech sections gracefully."""
    processor = FRWiktionaryProcessor()
    lines = [
        "== {{langue|fr}} ==",
        "=== {{S|nom|fr}} ===",
        "# Un morceau de matériel.",
        "=== {{S|sigle|fr}} ===",
        "# Un sigle inconnu.",
        "=== {{S|foo|fr|flexion}} ===",
        "# Une flexion inconnue.",
    ]
    definitions, examples = processor._parse_section_content(lines)

    assert "ana" in definitions
    assert definitions["ana"] == [
        "Un morceau de matériel.",
        "Un sigle inconnu.",
        "Une flexion inconnue.",
    ]


def test_get_all_entries_keeps_full_language_code():
    """Language codes must not be truncated to their first character."""
    processor = FRWiktionaryProcessor(test=True)
    processor.set_title("Paris")
    processor.set_text(
        "== {{langue|fr}} ==\n"
        "=== {{S|nom propre|fr}} ===\n"
        "# Capitale de la France.\n"
        "== {{langue|en}} ==\n"
        "=== {{S|nom propre|en}} ===\n"
        "# Capital of France.\n"
    )
    entries = processor.get_all_entries()

    assert len(entries) == 2
    assert {entry.language for entry in entries} == {"fr", "en"}
    assert all(entry.part_of_speech == "ana-pr" for entry in entries)


def test_parse_section_content_with_examples_only():
    processor = FRWiktionaryProcessor()
    lines = [
        "== {{langue|fr}} ==",
        "=== {{S|nom|fr}} ===",
        "# Un petit appareil.",
        "#* Exemple un pour l'appareil.",
        "#* Un autre exemple pour l'appareil.",
    ]
    definitions, examples = processor._parse_section_content(lines)

    assert "ana" in definitions
    assert definitions["ana"] == ["Un petit appareil."]
    assert "Un petit appareil." in examples
    assert examples["Un petit appareil."] == [
        "Exemple un pour l'appareil.",
        "Un autre exemple pour l'appareil.",
    ]


def test_parse_section_content_without_language_header():
    processor = FRWiktionaryProcessor()
    lines = [
        "=== {{S|nom|fr}} ===",
        "# Un morceau de matériel.",
    ]
    definitions, examples = processor._parse_section_content(lines)

    assert "ana" in definitions
    assert definitions["ana"] == ["Un morceau de matériel."]
    assert examples == {}


def test_refine_definition_basic():
    definition = "{{lexique|français}} Exemple de définition."
    part_of_speech = "ana"
    result = FRWiktionaryProcessor.refine_definition(definition, part_of_speech)
    assert isinstance(result, list)
    assert len(result) == 1
    assert "Exemple de définition" in result[0]


def test_refine_definition_with_wiki_links():
    definition = "Un [[chat]] domestique."
    part_of_speech = "ana"
    result = FRWiktionaryProcessor.refine_definition(definition, part_of_speech)
    assert isinstance(result, list)
    assert len(result) == 1
    assert "chat" in result[0]
    assert "Un chat domestique" in result[0]


def test_refine_definition_with_unwanted_chars():
    definition = "Une définition avec des {caractères} indésirables."
    part_of_speech = "mpam"
    result = FRWiktionaryProcessor.refine_definition(definition, part_of_speech)
    assert isinstance(result, list)
    assert len(result) == 1
    assert "caractères" in result[0]
    assert "Une définition avec des caractères indésirables" in result[0]


def test_refine_definition_empty_input():
    definition = ""
    result = FRWiktionaryProcessor.refine_definition(definition)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0] == ""


def test_refine_definition_no_templates_or_links():
    definition = "Une définition simple sans lien ni modèle."
    part_of_speech = None
    result = FRWiktionaryProcessor.refine_definition(definition, part_of_speech)
    assert isinstance(result, list)
    assert len(result) == 1
    assert "Une définition simple sans lien ni modèle" in result[0]


def test_advanced_extract_definition_basic(processor):
    """Test advanced_extract_definition with default configuration."""
    part_of_speech = "e-verb"
    definition_line = "# A sample definition line."
    result = processor.advanced_extract_definition(part_of_speech, definition_line)
    assert result == definition_line


def test_advanced_extract_definition_no_human_readable(processor):
    """Test advanced_extract_definition with human_readable_form=False."""
    part_of_speech = "e-verb"
    definition_line = "# Another definition line."
    config = DefinitionProcessingConfig(human_readable_form=False)
    result = processor.advanced_extract_definition(part_of_speech, definition_line, config=config)
    assert result == definition_line


def test_advanced_extract_definition_translate_to_malagasy(processor):
    """Test advanced_extract_definition with translate_to_malagasy=True."""
    part_of_speech = "e-verb"
    definition_line = "# Malagasy translation not applied in test."
    config = DefinitionProcessingConfig(translate_to_malagasy=True)
    result = processor.advanced_extract_definition(part_of_speech, definition_line, config=config)
    assert result == definition_line


def test_advanced_extract_definition_non_e_part_of_speech(processor):
    """Test advanced_extract_definition with a non-e- part of speech."""
    part_of_speech = "noun"
    definition_line = "# A non-e-part of speech definition."
    result = processor.advanced_extract_definition(part_of_speech, definition_line)
    assert result == definition_line


def test_get_additional_data_uses_importers(mocker) -> None:
    """Collect additional data from importers."""

    class DummyImporter:
        """Dummy importer with a data type."""

        data_type = "dummy"
        section_name = "Dummy"

        def get_data(self, section_name: str, content: str, language: str) -> list:
            """Return dummy data."""
            return ["data"]

    mocker.patch("api.entryprocessor.wiki.fr.all_importers", [DummyImporter])
    processor = FRWiktionaryProcessor()
    result = processor.get_additional_data("content", "fr")
    assert result == {"dummy": ["data"]}


def test_extract_definition_uses_advanced(processor, mocker) -> None:
    """Delegate extraction to advanced_extract_definition."""
    mocker.patch.object(processor, "advanced_extract_definition", return_value="processed")
    result = processor.extract_definition("ana", "# definition")
    assert result == "processed"


def test_parse_section_content_flexion() -> None:
    """Parse flexion sections into e- parts of speech."""
    processor = FRWiktionaryProcessor()
    lines = [
        "== {{langue|fr}} ==",
        "=== {{S|nom|fr|flexion}} ===",
        "# Forme fléchie.",
    ]
    definitions, _examples = processor._parse_section_content(lines)
    assert "e-ana" in definitions


def test_create_entries_from_definitions_with_additional_data() -> None:
    """Attach additional data when provided."""
    processor = FRWiktionaryProcessor()
    definitions_dict = {"ana": ["definition"]}
    additional_data = {"data": ["value"]}
    entries = processor._create_entries_from_definitions(
        definitions_dict, "fr", additional_data, True
    )
    assert entries[0].additional_data == {"data": ["value"]}


def test_extract_label_data_valid() -> None:
    """Extract label data when valid."""
    definition = "label data"
    label = FRWiktionaryProcessor._extract_label_data(definition, 0, len(definition))
    assert label == "label data"


def test_convert_to_human_readable_form_not_in_template(processor) -> None:
    """Return the original definition when no template matches."""
    result = processor._convert_to_human_readable_form(
        "e-unknown", "# test", translate_to_malagasy=True
    )
    assert result == "# test"


def test_convert_to_human_readable_form(processor, mocker) -> None:
    """Convert form-of definitions using the template parser."""

    class DummyElements:
        """Simple template parsing result."""

        def to_definition(self, language: str) -> str:
            """Return a localized definition string."""
            return f"definition-{language}"

    mocker.patch("api.entryprocessor.wiki.fr.TEMPLATE_TO_OBJECT", {"e-ana": "dummy"})
    mocker.patch(
        "api.entryprocessor.wiki.fr.definitions_parser.get_elements",
        return_value=DummyElements(),
    )

    result = processor._convert_to_human_readable_form(
        "e-ana", "# test", translate_to_malagasy=False
    )
    assert result == "definition-fr"


def test_convert_to_human_readable_form_error(processor, mocker) -> None:
    """Return original definition on parser errors."""
    mocker.patch("api.entryprocessor.wiki.fr.TEMPLATE_TO_OBJECT", {"e-ana": "dummy"})
    mocker.patch(
        "api.entryprocessor.wiki.fr.definitions_parser.get_elements",
        side_effect=RuntimeError("boom"),
    )
    result = processor._convert_to_human_readable_form(
        "e-ana", "# test", translate_to_malagasy=False
    )
    assert result == "# test"


def test_process_templates_with_label(mocker) -> None:
    """Prefix labels when extracted from templates."""
    mocker.patch(
        "api.entryprocessor.wiki.fr.FRWiktionaryProcessor._extract_label_data",
        return_value="label",
    )
    definition = "{{lexique|francais}} Exemple."
    result = FRWiktionaryProcessor._process_templates(
        definition, [r"\{\{lexique\|[a-zA-Z0-9\ \|]+\}\}"]
    )
    assert result == "(label) Exemple."


def test_process_wiki_links_form_of_keeps_links() -> None:
    """Preserve simple wiki links for form-of entries."""
    result = FRWiktionaryProcessor._process_wiki_links(
        "Un [[chat]] domestique.", part_of_speech="e-ana"
    )
    assert "[[chat]]" in result


def test_validate_refined_definition_raises() -> None:
    """Raise when unwanted characters remain."""
    with pytest.raises(Exception):
        FRWiktionaryProcessor._validate_refined_definition("bad {", ["{"])
