from unittest import TestCase

from api.model.word import Entry
from api.translation_v2.functions import postprocessors
from api.translation_v2.functions.definitions import preprocessors


class DefinitionsPostProcessorsTest(TestCase):
    def test_drop_definitions_with_labels(self):
        drop_definitions = preprocessors.drop_definitions_with_labels("xxx", "yy", "zzzzz")
        assert drop_definitions("(xxx) ;dasldkasd") == ""
        assert drop_definitions("(ska, xxx) asd;kqwej") == ""
        assert drop_definitions("(ass, yy) asdkad") == ""
        assert drop_definitions("(asdlkj, zzzzz) qw;elkqwe") == ""
        assert drop_definitions("(asdj) def1") == "(asdj) def1"

    def test_handle_gloss_templates(self):
        assert preprocessors.handle_nongloss_templates("{{gloss|def1}}") == "''def1''"
        assert preprocessors.handle_nongloss_templates("{{g|def1}}") == "''def1''"
        assert preprocessors.handle_nongloss_templates("{{g|def1}} def1") == "''def1'' def1"

    def test_handle_gloss_templates_handles_gloss_template(self):
        assert preprocessors.handle_gloss_templates("Gloss {{gl|note}} text") == "Gloss (note) text"

    def test_handle_gloss_templates_handles_unclosed_template(self):
        assert preprocessors.handle_gloss_templates("Gloss {{gloss|note") == "Gloss (not)"

    def test_handle_taxfmt_templates_replaces_categories(self):
        definition = "The {{taxfmt|Tribolodon hakonensis|species}}"
        assert preprocessors.handle_taxfmt_templates(definition) == "The ''Tribolodon hakonensis (species)''"

    def test_handle_taxfmt_templates_handles_unclosed_template(self):
        assert preprocessors.handle_taxfmt_templates("See {{taxfmt|Genus") == "See ''Genu''"

    def test_handle_surrounding_string_removes_pairs(self):
        assert preprocessors.handle_surrounding_string("''", "''one'' and ''two''") == "one and two"

    def test_handle_link(self):
        assert preprocessors.handle_link("[[def1|def2]]") == "def1"
        assert preprocessors.handle_link("[[def1#def2|def3]]") == "def3"
        assert preprocessors.handle_link("[[def1]]") == "def1"

    def test_unlink_definition_handles_piped_section_links(self):
        definition = "to (politely) [[request#English|request]] something"

        assert preprocessors.unlink_definition(definition) == "to (politely) request something"
        assert preprocessors.unlink_definition("[[#English|request]]") == "request"

    def test_delete_all_templates(self):
        assert preprocessors.delete_all_templates("{{def1}}") == ""
        assert preprocessors.delete_all_templates("{{def1|") == ""

    def test_delete_all_html_comments(self):
        assert preprocessors.delete_html_comments("[[faritra]] voafaritra. <!-- [[tokony]] hozaraina ho 2 ve") == "[[faritra]] voafaritra."

    def test_delete_all_templates_nested(self):
        assert preprocessors.delete_all_templates("{{def1|{{def2|{{def3}}}}}}") == ""

    def test_render_definition_templates_removes_editorial_and_label_templates(self):
        definition = "{{label|en|slang}} {{rfv-sense}} A {{term-label|en|rare}} term"
        assert preprocessors.render_definition_templates(definition) == "  A  term"
        assert preprocessors.refine_definition(definition, remove_all_templates=True) == "A term"

    def test_render_definition_templates_preserves_script_definition(self):
        assert preprocessors.refine_definition(
            "{{Latn-def|en|A definition in Latin script}}", remove_all_templates=True
        ) == "A definition in Latin script"

    def test_render_definition_templates_preserves_example_text(self):
        assert preprocessors.refine_definition(
            "{{ux|en|An example sentence.|A translation.}}", remove_all_templates=True
        ) == "An example sentence."

    def test_render_definition_templates_renders_relations(self):
        assert preprocessors.refine_definition(
            "{{only_used_in|en|fixed phrases}}", remove_all_templates=True
        ) == "only used in fixed phrases"

    def test_render_definition_templates_renders_altform(self) -> None:
        """Test that altform templates remain readable and retain their target."""
        assert (
            preprocessors.refine_definition("{{altform|es|rankear}}")
            == "alternative form of rankear"
        )

    def test_render_definition_templates_renders_alternative_spelling(self) -> None:
        assert (
            preprocessors.refine_definition(
                "{{alternative spelling of|en|genuflection}}"
            )
            == "alternative spelling of genuflection"
        )

    def test_render_definition_templates_handles_nested_content(self):
        assert preprocessors.refine_definition(
            "{{Latn-def|en|A [[linked|definition]]}}", remove_all_templates=True
        ) == "A linked"

    def test_render_definition_templates_limits_nested_templates(self):
        definition = "{{Latn-def|en|" * 21 + "definition" + "}}" * 21
        rendered = preprocessors.render_definition_templates(definition)
        assert rendered == "{{Latn-def|en|definition}}"
        assert "definition" in rendered


class TestPostProcessors(TestCase):
    def test_add_wiktionary_credit(self):
        wiki = "mg"
        entry = Entry(
            entry="entry",
            part_of_speech="ana",
            definitions=["def1", "def2"],
            language="en",
        )
        credit = postprocessors.add_wiktionary_credit(wiki)
        out_entries = credit([entry])
        assert "reference" in out_entries[0].additional_data
        expected = "{{wikibolana|" + wiki + "|" + entry.entry + "}}"
        self.assertEqual(out_entries[0].additional_data["reference"][0], expected)

    def test_add_xlit_if_no_transcription(self):
        entry = Entry(
            entry="काम",
            part_of_speech="ana",
            definitions=["def1", "def2"],
            language="hi",
        )
        function = postprocessors.add_xlit_if_no_transcription()
        function([entry])

    def test_add_language_ipa_if_not_exists(self):
        entry = Entry(
            entry="entry",
            part_of_speech="ana",
            definitions=["def1", "def2"],
            language="hi",
        )
        function = postprocessors.add_language_ipa_if_not_exists()
        function([entry])

    def test_add_japanese_verb_form(self):
        ja_entry = Entry(
            entry="行く",
            part_of_speech="mat",
            definitions=["to go"],
            language="ja",
            additional_data=None,
        )
        ja_entry_existing = Entry(
            entry="見る",
            part_of_speech="mat",
            definitions=["to see"],
            language="ja",
            additional_data={"inflection": ["existing"]},
        )
        en_entry = Entry(
            entry="go",
            part_of_speech="mat",
            definitions=["to go"],
            language="en",
        )
        function = postprocessors.add_japanese_verb_form()
        out_entries = function([ja_entry, ja_entry_existing, en_entry])
        self.assertEqual(out_entries[0].additional_data["inflection"], ["{{ja-ojad}}"])
        self.assertEqual(out_entries[1].additional_data["inflection"], ["existing"])
        self.assertNotIn("inflection", out_entries[2].additional_data)

    def test_only_accept_from_source_wiki(self):
        entry_en = Entry(
            entry="entry-en",
            part_of_speech="ana",
            definitions=["def1"],
            language="en",
        )
        entry_en.origin_wiktionary = "en"
        entry_fr = Entry(
            entry="entry-fr",
            part_of_speech="ana",
            definitions=["def2"],
            language="en",
        )
        entry_fr.origin_wiktionary = "fr"
        entry_no_origin = Entry(
            entry="entry-no-origin",
            part_of_speech="ana",
            definitions=["def3"],
            language="en",
        )
        function = postprocessors.only_accept_from_source_wiki("en")
        with self.assertLogs("api.translation_v2.functions.postprocessors", level="WARNING") as logs:
            out_entries = function([entry_en, entry_fr, entry_no_origin])
        self.assertEqual(out_entries, [entry_en, entry_no_origin])
        self.assertTrue(any("Cannot apply only_accept_from_source_wiki" in message for message in logs.output))

    def test_filter_out_languages(self):
        entry = Entry(
            entry="entry",
            part_of_speech="ana",
            definitions=["def1", "def2"],
            language="en",
        )
        function = postprocessors.filter_out_languages("en")
        function([entry])
