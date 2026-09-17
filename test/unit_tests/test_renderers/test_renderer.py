from unittest.case import TestCase
from unittest.mock import MagicMock, patch

import requests

from api.http_client import BULK_HTTP_TIMEOUT
from api.page_renderer.mg import MGWikiPageRenderer


class TestRenderers(TestCase):
    def setUp(self):
        """Prevent renderer tests from reaching the live PostgREST service."""
        MGWikiPageRenderer._pages_to_link_cache = frozenset()

    def tearDown(self):
        """Restore the lazy process cache after each renderer test."""
        MGWikiPageRenderer._pages_to_link_cache = None

    def test_head_section(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.language = "mg"
        info.part_of_speech = "ana"
        info.additional_data = {
            "etymology": "no etimologies for you!!",
            "transcription": ["totot", "toto"],
        }
        head_section = renderer.render_head_section(info)
        expected = (
            """
=={{="""
            + info.language
            + """=}}==

{{-etim-}}
:no etimologies for you!!
{{-"""
            + info.part_of_speech
            + """-|"""
            + info.language
            + """}}
'''{{subst:BASEPAGENAME}}''' ("""
            + ", ".join(info.additional_data["transcription"])
            + """)"""
        )
        self.assertEqual(head_section, expected)
        self.assertIn("{{-etim-}}", head_section)

    def test_etymology(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {"etymology": "etimologicheski"}
        etymology = renderer.render_etymology(info)
        self.assertEqual(
            etymology,
            """
{{-etim-}}
:"""
            + info.additional_data["etymology"],
        )

    def test_empty_canonical_etymology_uses_fallback(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.language = "en"
        info.additional_data = {"etymology": []}
        self.assertEqual(
            renderer.render_etymology(info),
            "\n{{-etim-}}\n: {{vang-etim|en}}\n",
        )

    def test_definitions(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.definitions = ["def2", "def1", "def4", "def2"]
        definitions = renderer.render_definitions(info, [])
        rendered_definitions = """
# def2
# def1
# def4"""
        self.assertEqual(definitions, rendered_definitions)

    def test_definitions_strip_generated_nllb_noun_prefix(self):
        """Never publish the observed mixed Malagasy-English noun scaffold."""

        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.definitions = [
            "-ny is a mafy",
            "-ny is an hazo",
            "-ny is a[n] boky",
            "famaritana -ny is a teny",
        ]
        info.additional_data = {}

        self.assertEqual(
            renderer.render_definitions(info, []),
            "\n# mafy\n# hazo\n# boky\n# famaritana -ny is a teny",
        )

    def test_definitions_with_examples(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.definitions = ["def1", "def2", "def4"]
        info.additional_data = {
            "examples": [["exdef1"], ["exdef2", "exdef22"], ["exdef4"]]
        }
        definitions = renderer.render_definitions(info, [])
        rendered_definitions = """
# def1
#* ''exdef1''
# def2
#* ''exdef2''
#* ''exdef22''
# def4
#* ''exdef4''"""
        self.assertEqual(definitions, rendered_definitions)

    def test_quotations_render_with_their_full_citation(self):
        """Render the citation source above a sourced quotation passage."""

        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.definitions = ["def1"]
        info.additional_data = {
            "examples": [["a cited passage", "a plain example"]],
            "citations": [
                {
                    "source": (
                        "Billie Cohen, "
                        "[http://example.org/a Searching for a Caretaker], "
                        "[[w:The New York Times|The New York Times]], "
                        "December 28, 2007"
                    ),
                    "text": "a cited passage",
                    "definition": "def1",
                }
            ],
        }
        definitions = renderer.render_definitions(info, [])
        rendered_definitions = (
            "\n# def1"
            "\n#* ''a cited passage \u2013 Billie Cohen, "
            "[http://example.org/a Searching for a Caretaker], "
            "[[w:The New York Times|The New York Times]], "
            "December 28, 2007''"
            "\n#* ''a plain example''"
        )
        self.assertEqual(definitions, rendered_definitions)

    def test_duplicate_definitions_merge_their_examples(self):
        """Keep example alignment when duplicate definition text is collapsed."""

        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.definitions = ["same", "same", "third"]
        info.additional_data = {"examples": [["one"], ["two"], ["three"]]}
        self.assertEqual(
            renderer.render_definitions(info, []),
            "\n# same\n#* ''one''\n#* ''two''\n# third\n#* ''three''",
        )

    def test_definitions_with_link(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        links = ["def2", "def1", "ak"]
        info.definitions = ["def2.", "[[def1]]", "def4", "mult ak"]
        definitions = renderer.render_definitions(info, links)
        rendered_definitions = """
# [[def2|def2]].
# [[def1]]
# [[def4]]
# mult ak"""
        self.assertEqual(definitions, rendered_definitions)

    def test_definition_links_each_word_only_once(self):
        """Repeated words remain plain text after their first automatic link."""
        MGWikiPageRenderer._pages_to_link_cache = frozenset({"longword"})
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.definitions = ["Longword longword, longword."]

        definitions = renderer.render_definitions(info, ["longword"])

        self.assertEqual(
            definitions,
            "\n# [[longword|Longword]] longword, longword.",
        )

    def test_definition_links_repeated_word_again_in_next_definition(self):
        """The one-link budget resets for every rendered definition."""
        MGWikiPageRenderer._pages_to_link_cache = frozenset({"longword"})
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.definitions = ["longword longword", "another longword"]

        definitions = renderer.render_definitions(info, ["longword"])

        self.assertEqual(
            definitions,
            "\n# [[longword]] longword\n# another [[longword]]",
        )

    def test_definition_links_longest_phrase_and_skips_current_word(self):
        """Longer phrases win and the page being rendered is not self-linked."""
        MGWikiPageRenderer._pages_to_link_cache = frozenset(
            {"source", "trano", "trano fonenana"}
        )
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.entry = "source"
        info.definitions = ["source trano fonenana beside trano"]

        definitions = renderer.render_definitions(info, True)

        self.assertEqual(
            definitions,
            "\n# source [[trano fonenana]] beside [[trano]]",
        )

    @patch("api.page_renderer.mg.requests.get")
    def test_pages_to_link_is_loaded_once_per_process(self, mock_get):
        """Multiple renderer instances share one immutable page cache."""
        MGWikiPageRenderer._pages_to_link_cache = None
        response = MagicMock(status_code=200)
        response.json.return_value = [{"word": "longword"}, {"word": "tiny"}]
        mock_get.return_value = response

        first = MGWikiPageRenderer().pages_to_link
        second = MGWikiPageRenderer().pages_to_link

        self.assertIs(first, second)
        self.assertEqual(first, frozenset({"longword", "tiny"}))
        mock_get.assert_called_once_with(
            "http://localhost:8100/rpc/linkable_lexicon_headwords",
            timeout=BULK_HTTP_TIMEOUT,
        )

    @patch("api.page_renderer.mg.requests.get")
    def test_pages_to_link_caches_fail_open_result(self, mock_get):
        """A failed bulk load does not cause one request per definition."""
        MGWikiPageRenderer._pages_to_link_cache = None
        mock_get.side_effect = requests.ConnectionError("down")
        renderer = MGWikiPageRenderer()

        self.assertEqual(renderer.pages_to_link, frozenset())
        self.assertEqual(renderer.pages_to_link, frozenset())
        mock_get.assert_called_once()

    def test_pronunciation_non_list(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {"pronunciation": "abcsded"}
        pronunciation = renderer.render_pronunciation(info)
        pronunciation_section = """

{{-fanononana-}}
* abcsded"""
        self.assertEqual(pronunciation, pronunciation_section)

    def test_pronunciation_list(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {"pronunciation": ["{{p1|tptp}}", "{{p1|tptp2}}"]}
        pronunciation = renderer.render_pronunciation(info)
        pronunciation_section = """

{{-fanononana-}}
* {{p1|tptp}}
* {{p1|tptp2}}"""
        self.assertEqual(pronunciation, pronunciation_section)

    def test_multiline_pronunciation_template_gets_one_bullet(self):
        """A multiline template keeps its shape behind a single bullet."""
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.language = "zho"
        info.additional_data = {
            "pronunciation": [
                "{{zh-pron\n|m=ròuyuán\n|c=juk6 jyun4\n|cat=n\n}}"
            ]
        }
        pronunciation = renderer.render_pronunciation(info)
        pronunciation_section = """

{{-fanononana-}}
* {{zh-pron
|m=ròuyuán
|c=juk6 jyun4
|cat=n
}}"""
        self.assertEqual(pronunciation, pronunciation_section)

    def test_audio_pronunciation(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {"audio_pronunciations": ["audio1.mp3"]}
        info.entry = "entry"
        pronunciation = renderer.render_pronunciation(info)
        pronunciation_section = """

{{-fanononana-}}
* {{audio|audio1.mp3|entry}}"""
        self.assertEqual(pronunciation, pronunciation_section)

    def test_ipa_pronunciation(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {"ipa": ["akakak"]}
        info.entry = "entry"
        info.language = "mg"
        pronunciation = renderer.render_pronunciation(info)
        pronunciation_section = """

{{-fanononana-}}
* {{fanononana|akakak|mg}}"""
        self.assertEqual(pronunciation, pronunciation_section)

    def test_structured_pronunciation_is_not_rendered_twice(self):
        """Prefer normalized IPA/audio while retaining other raw sound lines."""

        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.entry = "word"
        info.language = "en"
        info.additional_data = {
            "pronunciation": [
                "{{IPA|en|/wɜːd/}}",
                "{{audio-pron|en|word.ogg|Audio}}",
                "{{rhymes|en|ɜːd}}",
            ],
            "ipa": ["/wɜːd/"],
            "audio": ["word.ogg"],
        }

        pronunciation = renderer.render_pronunciation(info)
        self.assertNotIn("{{IPA|", pronunciation)
        self.assertEqual(pronunciation.count("word.ogg"), 1)
        self.assertIn("{{fanononana|/wɜːd/|en}}", pronunciation)
        self.assertIn("{{rhymes|en|ɜːd}}", pronunciation)

    def test_structured_pronunciation_preserves_raw_qualifiers(self):
        """Remove only duplicate sound templates, not adjacent qualifiers."""

        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.entry = "word"
        info.language = "en"
        info.additional_data = {
            "pronunciation": ["{{a|US}} {{IPA|en|/wɜːd/}}"],
            "ipa": ["/wɜːd/"],
        }

        pronunciation = renderer.render_pronunciation(info)
        self.assertIn("{{a|US}}", pronunciation)
        self.assertNotIn("{{IPA|", pronunciation)
        self.assertIn("{{fanononana|/wɜːd/|en}}", pronunciation)

    def test_structured_pronunciation_preserves_audio_description(self):
        """Retain meaningful audio context and discard empty sound labels."""

        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.entry = "word"
        info.language = "en"
        info.additional_data = {
            "pronunciation": [
                "IPA: {{IPA|en|/wɜːd/}}",
                "{{audio|en|word.ogg|Audio (US)}}",
            ],
            "ipa": ["/wɜːd/"],
            "audio": ["word.ogg"],
        }

        pronunciation = renderer.render_pronunciation(info)
        self.assertNotIn("\n* IPA:", pronunciation)
        self.assertIn("Audio (US)", pronunciation)
        self.assertEqual(pronunciation.count("word.ogg"), 1)

    def test_structured_pronunciation_retains_unrepresented_template_metadata(self):
        """Keep raw templates when normalized atoms cannot preserve their semantics."""

        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.entry = "word"
        info.language = "en"
        info.additional_data = {
            "pronunciation": [
                "{{IPA|en|/wɜːd/|a=US}}",
                "{{IPA|en|/a/|;|/b/}}",
                "{{audio|en|word.ogg|a=US}}",
            ],
            "ipa": ["/wɜːd/", "/a/", "/b/"],
            "audio": ["word.ogg"],
        }

        pronunciation = renderer.render_pronunciation(info)
        self.assertIn("{{IPA|en|/wɜːd/|a=US}}", pronunciation)
        self.assertIn("{{IPA|en|/a/|;|/b/}}", pronunciation)
        self.assertIn("{{audio|en|word.ogg|a=US}}", pronunciation)
        self.assertNotIn("{{fanononana|;|en}}", pronunciation)
        self.assertEqual(pronunciation.count("/wɜːd/"), 1)
        self.assertEqual(pronunciation.count("/a/"), 1)
        self.assertEqual(pronunciation.count("/b/"), 1)
        self.assertEqual(pronunciation.count("word.ogg"), 1)

    def test_synonyms(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {"synonyms": ["syn1"]}
        synonyms = renderer.render_synonyms(info)
        sections = """

{{-dika-mitovy-}}
* [[syn1]]"""
        self.assertEqual(synonyms, sections)

    def test_antonyms(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {"antonyms": ["ant1"]}
        synonyms = renderer.render_antonyms(info)
        sections = """

{{-dika-mifanohitra-}}
* [[ant1]]"""
        self.assertEqual(synonyms, sections)

    def test_related_terms(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {"related_terms": ["rt1"]}
        synonyms = renderer.render_related_terms(info)
        sections = """

{{-teny mifandraika-}}
* [[rt1]]"""
        self.assertEqual(synonyms, sections)

    def test_derived_terms(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {"derived_terms": ["rt1"]}
        synonyms = renderer.render_related_terms(info)
        sections = """

{{-teny mifandraika-}}
* [[rt1]]"""
        self.assertEqual(synonyms, sections)

    def test_latin_related_terms_link_diacritics_to_plain_page_title(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.language = "la"
        info.additional_data = {"related_terms": ["praeiciō"]}

        related = renderer.render_related_terms(info)

        self.assertIn("[[praeicio|praeiciō]]", related)

    def test_russian_and_ukrainian_related_terms_remove_only_stress_marks(self):
        renderer = MGWikiPageRenderer()

        for language, term, expected_target in (
            ("ru", "сло́во", "слово"),
            ("uk", "Украї́на", "Україна"),
            ("ru", "сё́мга", "сёмга"),
        ):
            with self.subTest(language=language, term=term):
                info = MagicMock()
                info.language = language
                info.additional_data = {"related_terms": [term]}

                related = renderer.render_related_terms(info)

                self.assertIn(f"[[{expected_target}|{term}]]", related)

    def test_related_term_diacritics_remain_literal_for_other_languages(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.language = "fr"
        info.additional_data = {"related_terms": ["café"]}

        related = renderer.render_related_terms(info)

        self.assertIn("[[café]]", related)
        self.assertNotIn("[[cafe|café]]", related)

    def test_parser_additional_data_aliases(self):
        """Render the stable singular keys emitted by Wiktionary importers."""

        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.entry = "entry"
        info.language = "mg"
        info.additional_data = {
            "etym/en/parsed": ["From a source."],
            "audio": ["sample.ogg"],
            "synonym": ["same"],
            "antonym": ["opposite"],
            "related": ["relation"],
            "derived": ["derivative"],
        }

        self.assertEqual(renderer.render_etymology(info), "")
        self.assertIn("{{audio|sample.ogg|entry}}", renderer.render_pronunciation(info))
        self.assertIn("[[same]]", renderer.render_synonyms(info))
        self.assertIn("[[opposite]]", renderer.render_antonyms(info))
        related = renderer.render_related_terms(info)
        self.assertIn("[[relation]]", related)
        self.assertIn("[[derivative]]", related)

    def test_section(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {"test_attribute": "toskjf"}
        section = renderer.render_section(info, "{{-test-header-}}", "test_attribute")
        self.assertIn("{{-test-header-}}", section)

    def test_further_reading(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {"further_reading": ""}
        further_reading = renderer.render_further_reading(info)
        self.assertIn("{{-famakiana fanampiny-}}", further_reading)

    def test_references(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {"references": [""]}
        references = renderer.render_references(info)
        self.assertIn("{{-tsiahy-}}", references)

    def test_delete_section_bottom(self):
        renderer = MGWikiPageRenderer()
        test_wikipage = """=={{=pt=}}==

{{-etim-}}
: {{vang-etim|pt}}


{{-ana-|pt}}
'''sapo'''
# [[ankalan-damira]]
# [[bakaka]]
# [[sabakaka]]
# [[saobakaka]]

=={{=es=}}==

{{-etim-}}
: {{vang-etim|es}}


{{-ana-|es}}
'''sapo'''
# [[ankalan-damira]]
# [[bakaka]]
# [[sabakaka]]
# [[saobakaka]]
"""
        expected = """=={{=pt=}}==

{{-etim-}}
: {{vang-etim|pt}}


{{-ana-|pt}}
'''sapo'''
# [[ankalan-damira]]
# [[bakaka]]
# [[sabakaka]]
# [[saobakaka]]

"""
        removed_section = renderer.delete_section("es", test_wikipage)
        self.assertEqual(removed_section, expected)

    def test_delete_section_top(self):
        renderer = MGWikiPageRenderer()
        test_wikipage = """=={{=pt=}}==

{{-etim-}}
: {{vang-etim|pt}}


{{-ana-|pt}}
'''sapo'''
# [[ankalan-damira]]
# [[bakaka]]
# [[sabakaka]]
# [[saobakaka]]

=={{=es=}}==

{{-etim-}}
: {{vang-etim|es}}


{{-ana-|es}}
'''sapo'''
# [[ankalan-damira]]
# [[bakaka]]
# [[sabakaka]]
# [[saobakaka]]
"""
        expected = """
=={{=es=}}==

{{-etim-}}
: {{vang-etim|es}}


{{-ana-|es}}
'''sapo'''
# [[ankalan-damira]]
# [[bakaka]]
# [[sabakaka]]
# [[saobakaka]]
"""
        removed_section = renderer.delete_section("pt", test_wikipage)
        self.assertEqual(removed_section, expected)

    def test_delete_section_middle(self):
        renderer = MGWikiPageRenderer()
        test_wikipage = """
=={{=es=}}==

{{-mat-|es}}
'''valer'''
# [[+''''de''']]
# [[manampy]] na manan-danja
# ny ho [[matanjaka]]
# ny ho [[mendrika]]
# ny ho [[salama]] [[tsara]]

{{-tsiahy-}}
{{wikibolana|en|valer}}

=={{=fro=}}==

{{-mat-|fro}}
'''valer'''
# [[midina]]

{{-tsiahy-}}
* {{Tsiahy:Godefroy}}
* {{Tsiahy:Anglo-Norman On-Line Hub}}
* {{wikibolana|en|valer}}

=={{=gl=}}==

{{-mat-|gl}}
'''valer'''
# [[manampy]]
# [[mifanaraka]] amin'ny
# ny ho azo [[ekena]]
# ny ho [[mendrika]]

{{-fanononana-}}
* {{IPA|gl|[baˈleɾ]}}

{{-tsiahy-}}
* {{Tsiahy:gl:DDGM}}
* {{Tsiahy:gl:CX}}
* {{Tsiahy:gl:DDLG}}
* {{Tsiahy:gl:TILG}}
* {{Tsiahy:TLPGP}}
* {{wikibolana|en|valer}}
"""
        expected = """
=={{=es=}}==

{{-mat-|es}}
'''valer'''
# [[+''''de''']]
# [[manampy]] na manan-danja
# ny ho [[matanjaka]]
# ny ho [[mendrika]]
# ny ho [[salama]] [[tsara]]

{{-tsiahy-}}
{{wikibolana|en|valer}}


=={{=gl=}}==

{{-mat-|gl}}
'''valer'''
# [[manampy]]
# [[mifanaraka]] amin'ny
# ny ho azo [[ekena]]
# ny ho [[mendrika]]

{{-fanononana-}}
* {{IPA|gl|[baˈleɾ]}}

{{-tsiahy-}}
* {{Tsiahy:gl:DDGM}}
* {{Tsiahy:gl:CX}}
* {{Tsiahy:gl:DDLG}}
* {{Tsiahy:gl:TILG}}
* {{Tsiahy:TLPGP}}
* {{wikibolana|en|valer}}
"""
        removed_section = renderer.delete_section("fro", test_wikipage)
        self.assertEqual(removed_section, expected)

    def test_delete_section_middle_2(self):
        renderer = MGWikiPageRenderer()
        test_wikipage = """
=={{=es=}}==

{{-mat-|es}}
'''valer'''
# [[+''''de''']]
# [[manampy]] na manan-danja
# ny ho [[matanjaka]]
# ny ho [[mendrika]]
# ny ho [[salama]] [[tsara]]

{{-tsiahy-}}
{{wikibolana|en|valer}}

=={{=fro=}}==

{{-mat-|fro}}
'''valer'''
# [[midina]]

{{-tsiahy-}}
* {{Tsiahy:Godefroy}}
* {{Tsiahy:Anglo-Norman On-Line Hub}}
* {{wikibolana|en|valer}}

=={{=mfe=}}==

{{-ana-|mfe}}
'''valer'''
# ny [[lanjany]]

{{-tsiahy-}}
* Baker, Philip & Hookoomsing, Vinesh Y. 1987. ''Dictionnaire de créole mauricien. Morisyen – English – Français''
* {{wikibolana|en|valer}}

=={{=gl=}}==

{{-mat-|gl}}
'''valer'''
# [[manampy]]
# [[mifanaraka]] amin'ny
# ny ho azo [[ekena]]
# ny ho [[mendrika]]

{{-fanononana-}}
* {{IPA|gl|[baˈleɾ]}}

{{-tsiahy-}}
* {{Tsiahy:gl:DDGM}}
* {{Tsiahy:gl:CX}}
* {{Tsiahy:gl:DDLG}}
* {{Tsiahy:gl:TILG}}
* {{Tsiahy:TLPGP}}
* {{wikibolana|en|valer}}
"""
        expected = """
=={{=es=}}==

{{-mat-|es}}
'''valer'''
# [[+''''de''']]
# [[manampy]] na manan-danja
# ny ho [[matanjaka]]
# ny ho [[mendrika]]
# ny ho [[salama]] [[tsara]]

{{-tsiahy-}}
{{wikibolana|en|valer}}



=={{=gl=}}==

{{-mat-|gl}}
'''valer'''
# [[manampy]]
# [[mifanaraka]] amin'ny
# ny ho azo [[ekena]]
# ny ho [[mendrika]]

{{-fanononana-}}
* {{IPA|gl|[baˈleɾ]}}

{{-tsiahy-}}
* {{Tsiahy:gl:DDGM}}
* {{Tsiahy:gl:CX}}
* {{Tsiahy:gl:DDLG}}
* {{Tsiahy:gl:TILG}}
* {{Tsiahy:TLPGP}}
* {{wikibolana|en|valer}}
"""
        removed_section = renderer.delete_section("fro", test_wikipage)
        removed_section = renderer.delete_section("mfe", removed_section)
        self.assertEqual(removed_section, expected)

    def test_delete_section_canonical_language_name_header(self):
        renderer = MGWikiPageRenderer()
        test_wikipage = """==Luxembourgish==

===Noun===
{{head|lb|noun form}}

# {{plural of|lb|Alphabet}}
=={{=lb=}}==

{{-e-ana-|lb}}
'''Alphabeter'''
# ploraly ny teny [[Alphabet]]

{{-tsiahy-}}
{{wikibolana|en|Alphabeter}}
"""
        expected = """
=={{=lb=}}==

{{-e-ana-|lb}}
'''Alphabeter'''
# ploraly ny teny [[Alphabet]]

{{-tsiahy-}}
{{wikibolana|en|Alphabeter}}
"""
        removed_section = renderer.delete_section("lb", test_wikipage)
        self.assertEqual(removed_section, expected)

    def test_delete_section_canonical_language_name_header_in_middle(self):
        renderer = MGWikiPageRenderer()
        test_wikipage = """=={{=en=}}==

{{-ana-|en}}
'''Alphabeter'''
# [[abecedy]]

==Luxembourgish==

===Noun===
{{head|lb|noun form}}

# {{plural of|lb|Alphabet}}

=={{=mg=}}==

{{-ana-|mg}}
'''Alphabeter'''
# [[abidy]]
"""
        expected = """=={{=en=}}==

{{-ana-|en}}
'''Alphabeter'''
# [[abecedy]]


=={{=mg=}}==

{{-ana-|mg}}
'''Alphabeter'''
# [[abidy]]
"""
        removed_section = renderer.delete_section("lb", test_wikipage)
        self.assertEqual(removed_section, expected)

    def test_delete_section_canonical_language_name_with_whitespace(self):
        renderer = MGWikiPageRenderer()
        test_wikipage = """== Luxembourgish ==

===Noun===
{{head|lb|noun form}}

# {{plural of|lb|Alphabet}}

=={{=mg=}}==

{{-ana-|mg}}
'''Alphabeter'''
# [[abidy]]
"""
        expected = """
=={{=mg=}}==

{{-ana-|mg}}
'''Alphabeter'''
# [[abidy]]
"""
        removed_section = renderer.delete_section("lb", test_wikipage)
        self.assertEqual(removed_section, expected)

    def test_delete_section_canonical_language_name_in_multi_header_line(self):
        renderer = MGWikiPageRenderer()
        test_wikipage = """==Spanish== ==Spanish (PA)==

{{-ana-|es}}
'''valer'''
# [[manampy]]

=={{=gl=}}==

{{-mat-|gl}}
'''valer'''
# [[manampy]]
"""
        expected = """
=={{=gl=}}==

{{-mat-|gl}}
'''valer'''
# [[manampy]]
"""
        removed_section = renderer.delete_section("es", test_wikipage)
        self.assertEqual(removed_section, expected)
