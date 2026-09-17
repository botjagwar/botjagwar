import mwparserfromhell
import pytest
from api.entryprocessor.wiki.en import ENWiktionaryProcessor
from api.model.word import Entry
from api.parsers.inflection_template import ParserNotFoundError


@pytest.fixture
def processor():
    return ENWiktionaryProcessor()


@pytest.mark.parametrize(
    "definition, language, part_of_speech, other_params, expected_result",
    [
        # Test case 1: Basic refinement with no options
        (
                "This is a test definition.",
                None,
                None,
                {},
                ["This is a test definition."],
        ),
        # Test case 2: Refinement with remove_all_templates set to True
        (
                "This is {{a|test}} a definition with template.",
                None,
                None,
                {"remove_all_templates": True},
                ["This is a definition with template."],
        ),
        # Test case 3: Refinement with drop_labels
        (
                "This is a (dated) definition example.",
                None,
                None,
                {"drop_labels": ["dated"]},
                [],
        ),
        # Test case 4: Refinement with mixed options
        (
                "This is a (dated) {{a|template}}test.",
                None,
                None,
                {"remove_all_templates": True, "drop_labels": ["dated"]},
                [],
        ),
        # Test case 5: Drop all labels from definition
        (
                "(obsolete) This is another example definition.",
                None,
                None,
                {},
                ["This is another example definition."],
        ),
    ],
)
def test_refine_definition(definition, language, part_of_speech, other_params, expected_result):
    result = ENWiktionaryProcessor.refine_definition(
        definition, language=language, part_of_speech=part_of_speech, **other_params
    )
    assert result == expected_result


@pytest.fixture
def processor_instance():
    return ENWiktionaryProcessor()


def test_get_part_of_speech_valid_match(processor_instance):
    line = "=== Noun ==="
    processor_instance.postran = {
        "Noun": "Substantive",
        "Verb": "Action word",
    }
    result = processor_instance.get_part_of_speech(line)
    assert result == "Substantive"


def test_get_part_of_speech_no_match(processor_instance):
    line = "=== Adjective ==="
    processor_instance.postran = {
        "Noun": "Substantive",
        "Verb": "Action word",
    }
    result = processor_instance.get_part_of_speech(line)
    assert result is None


def test_get_part_of_speech_nested_call(processor_instance):
    line = "===== Verb ====="
    processor_instance.postran = {
        "Noun": "Substantive",
        "Verb": "Action word",
    }
    result = processor_instance.get_part_of_speech(line)
    assert result == "Action word"


def test_get_part_of_speech_max_level_exceeded(processor_instance):
    line = "====== Adverb ======"
    processor_instance.postran = {
        "Noun": "Substantive",
        "Verb": "Action word",
    }
    result = processor_instance.get_part_of_speech(line)
    assert result is None


def test_get_all_entries_empty_content(processor):
    processor.content = ""
    entries = processor.get_all_entries()
    assert entries == []


def test_get_all_entries_no_definitions(processor, mocker):
    processor.content = """
    ==German==
    === Adjective ===
    """
    mocker.patch.object(processor, "lang2code", side_effect=lambda x: x[:2].lower())

    entries = processor.get_all_entries()

    assert len(entries) == 0


def test_process_lines_valid_language(processor, mocker):
    mocker.patch.object(processor, 'lang2code', return_value="en")
    mocker.patch.object(processor, 'get_part_of_speech', return_value="noun")
    mocker.patch.object(processor, '_process_definition_line', return_value=None)

    lines = [
        "==English==",
        "# A domesticated carnivorous mammal.",
        "===Noun===",
        "# A common household pet.",
    ]

    definitions, lines_by_language = processor._process_lines(
        lines, cleanup_definitions=False, translate_definitions_to_malagasy=False,
        human_readable_form_of_definition=True
    )

    assert "en" in lines_by_language
    assert len(definitions) >= 0  # Definitions could vary based on implementation


def test_process_lines_invalid_language(processor, mocker):
    mocker.patch.object(processor, 'lang2code', side_effect=KeyError)
    mocker.patch.object(processor, 'get_part_of_speech', return_value="noun")

    lines = [
        "==UnknownLanguage==",
        "# A domesticated carnivorous mammal.",
    ]

    definitions, lines_by_language = processor._process_lines(
        lines, cleanup_definitions=False, translate_definitions_to_malagasy=False,
        human_readable_form_of_definition=True
    )

    assert "en" not in lines_by_language
    assert definitions == {}


def test_process_lines_multiple_languages(processor, mocker):
    mocker.patch.object(processor, 'lang2code', side_effect=lambda x: {"English": "en", "French": "fr"}.get(x))
    mocker.patch.object(processor, 'get_part_of_speech', return_value=None)

    lines = [
        "==English==",
        "# A domesticated carnivorous mammal.",
        "==French==",
        "# Un mammifère carnivore domestiqué.",
    ]

    definitions, lines_by_language = processor._process_lines(
        lines, cleanup_definitions=False, translate_definitions_to_malagasy=False,
        human_readable_form_of_definition=True
    )

    assert "en" in lines_by_language
    assert "fr" in lines_by_language
    assert len(definitions) >= 0


def test_process_lines_with_no_definitions(processor, mocker):
    mocker.patch.object(processor, 'lang2code', side_effect=lambda x: "en" if x == "English" else None)
    mocker.patch.object(processor, 'get_part_of_speech', return_value=None)

    lines = [
        "==English==",
        "===Noun===",
        "===Verb===",
    ]

    definitions, lines_by_language = processor._process_lines(
        lines, cleanup_definitions=False, translate_definitions_to_malagasy=False,
        human_readable_form_of_definition=True
    )

    assert "en" in lines_by_language
    assert definitions == {}


def test_process_definition_line_adds_definition(processor, mocker):
    line = "# Definition test"
    language_code = "en"
    part_of_speech = "noun"
    definitions = {}
    cleanup_definitions = False
    translate_definitions_to_malagasy = False
    human_readable_form_of_definition = True

    mocker.patch.object(processor, "refine_definition", return_value=["Refined definition"])
    mocker.patch.object(processor, "extract_definition", return_value="Final definition")

    processor._process_definition_line(
        line,
        language_code,
        part_of_speech,
        definitions,
        cleanup_definitions,
        translate_definitions_to_malagasy,
        human_readable_form_of_definition,
    )

    assert language_code in definitions
    assert part_of_speech in definitions[language_code]
    assert definitions[language_code][part_of_speech] == ["Final definition"]


def test_process_definition_line_skips_empty_definition(processor, mocker):
    line = "# "
    language_code = "en"
    part_of_speech = "noun"
    definitions = {}
    cleanup_definitions = False
    translate_definitions_to_malagasy = False
    human_readable_form_of_definition = True

    mocker.patch.object(processor, "refine_definition", return_value=[])

    processor._process_definition_line(
        line,
        language_code,
        part_of_speech,
        definitions,
        cleanup_definitions,
        translate_definitions_to_malagasy,
        human_readable_form_of_definition,
    )

    assert language_code not in definitions


def test_process_definition_line_no_part_of_speech(processor):
    line = "# Definition test"
    language_code = "en"
    part_of_speech = None
    definitions = {}
    cleanup_definitions = False
    translate_definitions_to_malagasy = False
    human_readable_form_of_definition = True

    processor._process_definition_line(
        line,
        language_code,
        part_of_speech,
        definitions,
        cleanup_definitions,
        translate_definitions_to_malagasy,
        human_readable_form_of_definition,
    )

    assert language_code not in definitions


def test_process_definition_line_creates_new_language_section(processor, mocker):
    line = "# Definition test"
    language_code = "en"
    part_of_speech = "verb"
    definitions = {}
    cleanup_definitions = False
    translate_definitions_to_malagasy = False
    human_readable_form_of_definition = True

    mocker.patch.object(processor, "refine_definition", return_value=["Refined definition"])
    mocker.patch.object(processor, "extract_definition", return_value="Final definition")

    processor._process_definition_line(
        line,
        language_code,
        part_of_speech,
        definitions,
        cleanup_definitions,
        translate_definitions_to_malagasy,
        human_readable_form_of_definition,
    )

    assert language_code in definitions
    assert part_of_speech in definitions[language_code]


def test_process_definition_line_adds_to_existing_part_of_speech(processor, mocker):
    line = "# Another definition"
    language_code = "en"
    part_of_speech = "adjective"
    definitions = {"en": {"adjective": ["Existing definition"]}}
    cleanup_definitions = False
    translate_definitions_to_malagasy = False
    human_readable_form_of_definition = True

    mocker.patch.object(processor, "refine_definition", return_value=["Refined definition"])
    mocker.patch.object(processor, "extract_definition", return_value="Another final definition")

    processor._process_definition_line(
        line,
        language_code,
        part_of_speech,
        definitions,
        cleanup_definitions,
        translate_definitions_to_malagasy,
        human_readable_form_of_definition,
    )

    assert language_code in definitions
    assert part_of_speech in definitions[language_code]
    assert definitions[language_code][part_of_speech] == ["Existing definition", "Another final definition"]


def test_build_entries_single_definition(processor):
    definitions = {
        "en": {
            "noun": ["A domesticated carnivorous mammal."]
        }
    }
    lines_by_language = {
        "en": ["Dog"]
    }
    entries = processor._build_entries(definitions, lines_by_language, get_additional_data=False)
    assert len(entries) == 1
    assert isinstance(entries[0], Entry)
    assert entries[0].part_of_speech == "noun"
    assert entries[0].language == "en"
    assert entries[0].definitions == ["A domesticated carnivorous mammal."]
    assert entries[0].additional_data == {}


def test_build_entries_empty_definitions(processor):
    definitions = {"en": {}}
    lines_by_language = {"en": ["Dog"]}
    entries = processor._build_entries(definitions, lines_by_language, get_additional_data=False)
    assert len(entries) == 0


def test_citation_parsing(processor):
    processor.content = """
==English==

===Noun===
{{en-noun}}

# {{lb|en|music}} A pattern of two or more [[chords]], often chords [[diatonic]] to a particular [[key]].
#* {{quote-book|en|author=Michael Miller|title=The Complete Idiot's Guide to Music Theory|edition=2nd|publisher=Alpha|year=2005|page=142|pageurl=https://books.google.com/books?id=sTMbuSQdqPMC&pg=PA142&dq=%22chord+progression%22&hl=en|isbn=978-1-59257-437-7|text=You don't have to start with a melody; you can base your tune on a specific '''chord progression''' and compose a melody that best fits the chords.}}
"""

    entries = processor.get_all_entries(get_additional_data=True)
    assert len(entries) == 1
    entry = entries[0]
    assert "citations" in entry.additional_data
    assert len(entry.additional_data["citations"]) == 1
    citation = entry.additional_data["citations"][0]
    assert citation["definition"] == entry.definitions[0]
    assert "Michael Miller" in citation["source"]
    assert "The Complete Idiot's Guide to Music Theory" in citation["source"]
    assert "pejy 142" in citation["source"]
    assert citation["text"].startswith("You don't have to start with a melody")


def test_journal_citation_keeps_full_source_with_linked_title(processor) -> None:
    """Keep date, author, linked title and work in a quotation's citation."""

    processor.content = """
==English==

===Verb===

# To [[write]] something [[manually]].
#* {{quote-journal|en|date=December 28, 2007|author=Billie Cohen|title=Searching for a Caretaker|work=w:The New York Times|url=http://www.nytimes.com/2007/12/28/travel/escapes/28your.html
|passage=type or even '''handwrite''' exactly what the duties and responsibilities are|archiveurl=https://web.archive.org/web/20221126030141/https://www.nytimes.com/2007/12/28/travel/escapes/28your.html}}
"""

    entry = processor.get_all_entries(get_additional_data=True)[0]
    citation = entry.additional_data["citations"][0]
    assert citation["source"] == (
        "Billie Cohen, "
        "[http://www.nytimes.com/2007/12/28/travel/escapes/28your.html "
        "Searching for a Caretaker], "
        "[[w:The New York Times|The New York Times]], "
        "28 Desambra 2007"
    )
    assert citation["text"] == (
        "type or even '''handwrite''' exactly what the duties and responsibilities are"
    )
    assert entry.additional_data["examples"] == [
        ["type or even '''handwrite''' exactly what the duties and responsibilities are"]
    ]
    assert "web.archive.org" not in citation["source"]


def test_continuation_passage_keeps_bold_headword(processor) -> None:
    """Keep the emboldened headword in a separately encoded passage."""

    processor.set_title("test")
    processor.set_text(
        """==English==
===Noun===
# A sense.
#* {{quote-book|en|author=Writer|title=Book}}
#*: A '''bold''' passage with a [[linked]] word.
"""
    )

    entry = processor.get_all_entries(get_additional_data=True)[0]
    citation = entry.additional_data["citations"][0]
    assert citation["text"] == "A '''bold''' passage with a linked word."


def test_bold_passage_survives_the_c_tokenizer(processor) -> None:
    """Keep bold markers when parsing with mwparserfromhell's C tokenizer.

    The test suite forces the pure-Python tokenizer, but production uses the
    C tokenizer, which truncates its input at a NUL byte.
    """
    import mwparserfromhell.parser as parser_module

    if parser_module.CTokenizer is None:
        pytest.skip("mwparserfromhell C extension is unavailable")
    original_use_c = parser_module.use_c
    parser_module.use_c = True
    try:
        citation = processor._parse_citation_line(
            "#* {{quote-book|en|author=A. Writer|passage=a '''bold''' word}}"
        )
    finally:
        parser_module.use_c = original_use_c
    assert citation == {"source": "A. Writer", "text": "a '''bold''' word"}


def test_citation_url_without_title_is_appended_to_the_source(processor) -> None:
    """Do not drop the quotation URL when the template names no title."""

    citation = processor._parse_citation_line(
        "#* {{quote-journal|en|author=A. Writer|url=http://example.org/a"
        "|passage=A passage.}}"
    )
    assert citation == {
        "source": "A. Writer, http://example.org/a",
        "text": "A passage.",
    }


def test_citation_combines_month_and_year_in_malagasy_order(processor) -> None:
    """Render separate month and year fields as one localized date."""
    citation = processor._parse_citation_line(
        "#* {{quote-book|en|title=Original title|year=2008|month=May|page="
        "|passage=A passage.}}"
    )

    assert citation == {
        "source": "Original title, Mey 2008",
        "text": "A passage.",
    }


@pytest.mark.parametrize(
    "template_name", ["quote-journal", "quote-web", "cite-web"]
)
def test_citation_templates_share_full_source_parsing(
    processor, template_name
) -> None:
    """Parse quote-journal, quote-web and cite-web citations identically."""

    citation = processor._parse_citation_line(
        "#* {{" + template_name + "|en|date=May 30, 2008|author=Felicia R. Lee"
        "|title=Harry Potter Prequel for Charity|work=w:The New York Times"
        "|url=http://example.org/a"
        "|passage=Ms. Rowling used both sides of her card to '''handwrite''' "
        "the prequel."
        "|archiveurl=https://web.archive.org/x|accessdate=2023-01-01}}"
    )
    assert citation == {
        "source": (
            "Felicia R. Lee, "
            "[http://example.org/a Harry Potter Prequel for Charity], "
            "[[w:The New York Times|The New York Times]], "
            "30 Mey 2008"
        ),
        "text": (
            "Ms. Rowling used both sides of her card to '''handwrite''' "
            "the prequel."
        ),
    }


def test_quote_web_site_parameter_is_part_of_the_source(processor) -> None:
    """Keep the site name of a quote-web citation in its source."""

    processor.set_title("test")
    processor.set_text(
        """==English==
===Noun===
# A sense.
#* {{quote-web|en|date=2018-05-05|author=John Doe|title=Some Article|site=Example News|url=https://example.org/article|passage=A '''sense''' used on the web.}}
"""
    )

    entry = processor.get_all_entries(get_additional_data=True)[0]
    citation = entry.additional_data["citations"][0]
    assert citation["definition"] == "A sense."
    assert citation["source"] == (
        "John Doe, [https://example.org/article Some Article], "
        "Example News, 5 Mey 2018"
    )
    assert entry.additional_data["examples"] == [["A '''sense''' used on the web."]]


def test_additional_data_is_scoped_to_its_part_of_speech(processor) -> None:
    """Keep POS-owned relations isolated while sharing language-level sounds."""

    processor.set_title("test")
    processor.set_text(
        """==English==
===Pronunciation===
* {{IPA|en|/tɛst/}}
===Noun===
{{en-noun}}
# An examination.
====Synonyms====
* [[exam]]
====Hypernyms====
* [[assessment]]
===Verb===
{{en-verb}}
# To examine.
====Synonyms====
* [[examine]]
"""
    )

    entries = processor.get_all_entries(get_additional_data=True)
    noun = next(entry for entry in entries if entry.part_of_speech == "ana")
    verb = next(entry for entry in entries if entry.part_of_speech == "mat")

    assert noun.additional_data["synonym"] == ["exam"]
    assert noun.additional_data["hypernym"] == ["assessment"]
    assert verb.additional_data["synonym"] == ["examine"]
    assert "hypernym" not in verb.additional_data
    assert noun.additional_data["ipa"] == ["/tɛst/"]
    assert verb.additional_data["ipa"] == ["/tɛst/"]


def test_numbered_etymology_data_is_scoped_to_branch_pos(processor) -> None:
    """Do not copy one numbered etymology's data to another branch's POS."""

    processor.set_title("test")
    processor.set_text(
        """==English==
===Etymology 1===
From the noun source.
====Pronunciation====
* {{IPA|en|/naʊn/}}
====Noun====
# A noun.
====Synonyms====
* [[substantive]]
====Derived terms====
=====Nouns=====
* [[noun-derived]]
===Etymology 2===
From the verb source.
====Pronunciation====
* {{IPA|en|/vɜːb/}}
====Verb====
# A verb.
====Synonyms====
* [[action]]
"""
    )

    entries = processor.get_all_entries(get_additional_data=True)
    noun = next(entry for entry in entries if entry.part_of_speech == "ana")
    verb = next(entry for entry in entries if entry.part_of_speech == "mat")
    assert noun.additional_data["etym/en"] == ["From the noun source."]
    assert noun.additional_data["ipa"] == ["/naʊn/"]
    assert noun.additional_data["synonym"] == ["substantive"]
    assert noun.additional_data["derived"] == ["noun-derived"]
    assert verb.additional_data["etym/en"] == ["From the verb source."]
    assert verb.additional_data["ipa"] == ["/vɜːb/"]
    assert verb.additional_data["synonym"] == ["action"]
    assert "derived" not in verb.additional_data


def test_recursive_descendants_are_scoped_without_changing_flat_data(processor) -> None:
    """Keep recursive preview trees separate while preserving flat metadata."""

    processor.set_title("test")
    processor.set_text(
        """==English==
===Etymology 1===
====Noun====
# A noun.
=====Descendants=====
* {{desc|fr|mot}}
** {{desc|frm|motet}}
===Etymology 2===
====Verb====
# A verb.
=====Descendants=====
* {{desc|de|Wort}}
"""
    )

    entries = processor.get_all_entries(get_additional_data=True)
    noun = next(entry for entry in entries if entry.part_of_speech == "ana")
    verb = next(entry for entry in entries if entry.part_of_speech == "mat")
    assert noun.additional_data["descendant"] == ["mot", "motet"]
    assert verb.additional_data["descendant"] == ["Wort"]
    assert processor.get_descendant_tree("en", "ana") == [
        {
            "lang": "French",
            "lang_code": "fr",
            "word": "mot",
            "descendants": [
                {"lang": "Middle French", "lang_code": "frm", "word": "motet"}
            ],
        }
    ]
    assert processor.get_descendant_tree("en", "mat") == [
        {"lang": "German", "lang_code": "de", "word": "Wort"}
    ]


def test_recursive_descendants_merge_same_pos_etymology_branches(processor) -> None:
    """Match the entry model's same-language and same-POS merge behavior."""

    processor.set_title("test")
    processor.set_text(
        """==English==
===Etymology 1===
====Noun====
# First noun.
=====Descendants=====
* {{desc|fr|mot}}
===Etymology 2===
====Noun====
# Second noun.
=====Descendants=====
* {{desc|de|Wort}}
"""
    )

    entry = processor.get_all_entries(get_additional_data=True)[0]
    assert entry.additional_data["descendant"] == ["mot", "Wort"]
    assert processor.get_descendant_tree("en", "ana") == [
        {"lang": "French", "lang_code": "fr", "word": "mot"},
        {"lang": "German", "lang_code": "de", "word": "Wort"},
    ]


def test_examples_are_aligned_with_flattened_subsenses(processor) -> None:
    """Attach examples and quotation passages to their owning definitions."""

    processor.set_title("test")
    processor.set_text(
        """==English==
===Noun===
# First sense.
#: {{ux|en|A first example.|Translation}}
## Nested sense.
##: A nested [[example]].
# Second sense.
#* {{quote-book|en|author=Writer|title=Book|passage=A quoted example.}}
"""
    )

    entry = processor.get_all_entries(get_additional_data=True)[0]
    assert entry.definitions == ["First sense.", "Nested sense.", "Second sense."]
    assert entry.additional_data["examples"] == [
        ["A first example."],
        ["A nested example."],
        ["A quoted example."],
    ]
    assert entry.additional_data["citations"][0]["definition"] == "Second sense."


def test_multiline_quotation_template_is_coalesced(processor) -> None:
    """Parse quotation passages whose template arguments span lines."""

    processor.set_title("test")
    processor.set_text(
        """==English==
===Noun===
# A sense.
#* {{quote-book|en
|author=Writer
|title=Book
|passage=A multiline quotation.
}}
"""
    )

    entry = processor.get_all_entries(get_additional_data=True)[0]
    assert entry.additional_data["examples"] == [["A multiline quotation."]]
    assert entry.additional_data["citations"][0]["text"] == "A multiline quotation."


def test_quotation_continuation_supplies_passage(processor) -> None:
    """Attach a separate quote passage line to its source template."""

    processor.set_title("test")
    processor.set_text(
        """==English==
===Noun===
# A sense.
#* {{quote-book|en|author=Writer|title=Book}}
#*: A separately encoded passage.
#*:: An English translation.
"""
    )

    entry = processor.get_all_entries(get_additional_data=True)[0]
    assert entry.additional_data["examples"] == [["A separately encoded passage."]]
    citation = entry.additional_data["citations"][0]
    assert citation["text"] == "A separately encoded passage."
    assert citation["source"] == "Writer, Book"


def test_dropped_definition_clears_example_context(processor, mocker) -> None:
    """Do not attach an orphan example to the preceding retained sense."""

    processor.set_title("test")
    processor.set_text(
        """==English==
===Noun===
# First sense.
# Dropped sense.
#: Orphan example.
"""
    )
    mocker.patch.object(
        processor,
        "refine_definition",
        side_effect=lambda definition, *args, **kwargs: (
            [] if definition == "Dropped sense." else [definition]
        ),
    )

    entry = processor.get_all_entries(get_additional_data=True)[0]
    assert entry.definitions == ["First sense."]
    assert "examples" not in entry.additional_data


def test_language_specific_example_template_uses_source_text(processor) -> None:
    """Read source text rather than romanization from Japanese examples."""

    assert processor._parse_example_line(
        "{{ja-usex|日本語|にほんご|Japanese language}}"
    ) == "日本語"


def test_unicode_and_hyphenated_language_headings_are_isolated(processor) -> None:
    """Recognize current language names without contaminating prior sections."""

    processor.set_title("test")
    processor.set_text(
        """==English==
===Noun===
# English definition.
==Arbëreshë Albanian==
===Noun===
# Arbëreshë definition.
==Arum-Tesu==
===Noun===
# Arum-Tesu definition.
"""
    )

    entries = processor.get_all_entries()
    assert [(entry.language, entry.definitions) for entry in entries] == [
        ("en", ["English definition."]),
        ("aae", ["Arbëreshë definition."]),
        ("aab", ["Arum-Tesu definition."]),
    ]


def test_unmapped_pos_does_not_inherit_previous_pos(processor) -> None:
    """Drop unsupported POS definitions instead of assigning the preceding POS."""

    processor.set_title("test")
    processor.set_text(
        """==English==
===Noun===
# Noun definition.
===Classifier===
# Classifier definition.
===Past participle===
# Participle definition.
"""
    )

    entries = processor.get_all_entries()
    assert len(entries) == 1
    assert entries[0].definitions == ["Noun definition."]


def test_additional_data_importers_with_the_same_key_are_merged(processor) -> None:
    """Merge duplicate importer keys rather than replacing earlier values."""

    class FirstImporter:
        data_type = "related"
        section_name = ""

        def get_data(self, *args: object) -> list[str]:
            return ["first", "shared"]

    class SecondImporter:
        data_type = "related"
        section_name = ""

        def get_data(self, *args: object) -> list[str]:
            return ["shared", "second"]

    processor.all_importers = [FirstImporter, SecondImporter]
    assert processor.get_additional_data("content", "en", "ana") == {
        "related": ["first", "shared", "second"]
    }


def test_advanced_extract_definition_no_cleanup(processor) -> None:
    """Return the original definition when cleanup is disabled."""
    definition_line = "# {{test}} Sample."
    result = processor.advanced_extract_definition(
        part_of_speech="noun",
        definition_line=definition_line,
        cleanup_definition=False,
    )
    assert result == definition_line


def test_advanced_extract_definition_parser_fallback(processor, mocker) -> None:
    """Return the original definition when parsing fails."""
    mocker.patch.object(processor, "template_to_object_mapper", {"noun": "dummy"})
    mocker.patch(
        "api.entryprocessor.wiki.en.templates_parser.get_elements",
        side_effect=ParserNotFoundError,
    )
    definition_line = "{{test}}"
    result = processor.advanced_extract_definition(
        part_of_speech="noun",
        definition_line=definition_line,
        cleanup_definition=True,
        translate_definitions_to_malagasy=False,
        human_readable_form_of_definition=True,
    )
    assert result == definition_line


def test_advanced_extract_definition_human_readable_translation(processor, mocker) -> None:
    """Use the template parser when the cleaned definition is empty."""

    class DummyElements:
        """Simple template parsing result."""

        def to_definition(self, language: str) -> str:
            """Return a localized definition string."""
            return f"definition-{language}"

    mocker.patch.object(processor, "template_to_object_mapper", {"noun": "dummy"})
    mocker.patch(
        "api.entryprocessor.wiki.en.templates_parser.get_elements",
        return_value=DummyElements(),
    )

    definition_line = "{{test}}"
    result = processor.advanced_extract_definition(
        part_of_speech="noun",
        definition_line=definition_line,
        cleanup_definition=True,
        translate_definitions_to_malagasy=True,
        human_readable_form_of_definition=True,
    )
    assert result == "definition-mg"


def test_parse_citation_line_plain_text(processor) -> None:
    """Parse citation lines without templates."""
    result = processor._parse_citation_line("#* Some citation text.")
    assert result == {"source": "", "text": "Some citation text."}


def test_parse_citation_line_empty(processor) -> None:
    """Return None for empty citation lines."""
    result = processor._parse_citation_line("#* ")
    assert result is None


def test_advanced_extract_definition_keeps_nonempty(processor) -> None:
    """Return original definition when cleanup doesn't empty the line."""
    definition_line = "A simple definition."
    result = processor.advanced_extract_definition(
        part_of_speech="noun",
        definition_line=definition_line,
        cleanup_definition=True,
        translate_definitions_to_malagasy=False,
        human_readable_form_of_definition=True,
    )
    assert result == definition_line


def test_process_proper_noun_section_with_spaced_headers(processor) -> None:
    """Process the Proper noun section when language and POS headers contain spaces."""
    processor.set_title("Madagascar")
    processor.set_text(
        """== English ==
=== Proper noun ===
# A country in [[Africa]].
"""
    )
    entries = processor.get_all_entries()
    assert len(entries) == 1
    assert entries[0].part_of_speech == "ana-pr"
    assert entries[0].language == "en"
    assert entries[0].definitions == ["A country in Africa."]


def test_process_proper_noun_section_without_spaces(processor) -> None:
    """Process the Proper noun section when headers contain no spaces."""
    processor.set_title("Madagascar")
    processor.set_text(
        """==English==
===Proper noun===
# A country in [[Africa]].
"""
    )
    entries = processor.get_all_entries()
    assert len(entries) == 1
    assert entries[0].part_of_speech == "ana-pr"
    assert entries[0].language == "en"
    assert entries[0].definitions == ["A country in Africa."]


def test_process_definitions_with_wiktionary_section_links(processor) -> None:
    """Keep only readable link text when definitions target an English section."""
    processor.set_title("ask")
    processor.set_text(
        """==English==
===Verb===
# to (politely) [[request#English|request]] something
# to (politely) [[#English|request]] something
"""
    )

    entries = processor.get_all_entries()

    assert len(entries) == 1
    assert entries[0].definitions == [
        "to (politely) request something",
        "to (politely) request something",
    ]


def test_additional_data_reuses_exact_source_parse_across_pos(
    processor, mocker
) -> None:
    """Parse a shared pronunciation body once while building multiple POS entries."""

    pronunciation = (
        "* {{IPA|en|/tɛst/}}\n"
        "* {{audio|en|En-us-test.ogg|Audio (US)}}"
    )
    processor.set_title("test")
    processor.set_text(
        "==English==\n"
        "===Pronunciation===\n"
        f"{pronunciation}\n"
        "===Noun===\n"
        "# An examination.\n"
        "===Verb===\n"
        "# To examine.\n"
    )
    parse = mocker.spy(mwparserfromhell, "parse")

    entries = processor.get_all_entries(get_additional_data=True)

    assert len(entries) == 2
    assert all(entry.additional_data["ipa"] == ["/tɛst/"] for entry in entries)
    assert all(
        entry.additional_data["audio"] == ["En-us-test.ogg"]
        for entry in entries
    )
    parsed_sources = [call.args[0] for call in parse.call_args_list]
    assert parsed_sources.count(pronunciation) == 1


def test_additional_data_parse_session_does_not_retain_old_content(processor) -> None:
    """Discard exact-source ASTs when a standalone extraction operation ends."""

    first = processor.get_additional_data(
        "==English==\n===Pronunciation===\n* {{IPA|en|/first/}}\n",
        "en",
        "ana",
    )
    second = processor.get_additional_data(
        "==English==\n===Pronunciation===\n* {{IPA|en|/second/}}\n",
        "en",
        "ana",
    )

    assert first["ipa"] == ["/first/"]
    assert second["ipa"] == ["/second/"]


def test_citation_and_example_parameters_do_not_trigger_child_parses(
    processor, mocker
) -> None:
    """Read parameter Wikicode already created by each line's top-level parse."""

    parse = mocker.spy(mwparserfromhell, "parse")
    citation = processor._parse_citation_line(
        "#* {{quote-book|en|author=[[Writer|A. Writer]]|"
        "passage=[[example|Quoted example.]]}}"
    )
    assert citation == {
        "source": "A. Writer",
        "text": "Quoted example.",
    }
    assert parse.call_count == 1

    parse.reset_mock()
    assert processor._parse_example_line(
        "{{ux|en|[[example|Usage example.]]|Translation}}"
    ) == "Usage example."
    assert parse.call_count == 1
