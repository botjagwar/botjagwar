import json

from api.importer.wiktionary.en import (
    AbbreviationImporter,
    AntonymImporterL5,
    AlternativeFormsImporter,
    AudioImporter,
    CoordinateTermsImporter,
    DerivedTermsImporter,
    DescendantImporter,
    EnPRImporter,
    EtymologyImporter,
    FurtherReadingImporter,
    HeadwordImporter,
    HolonymImporter,
    HomophoneImporter,
    HypernymImporter,
    HyphenationImporter,
    HyponymImporter,
    IPAImporter,
    InstanceImporter,
    LiteralMeaningImporter,
    MeronymImporter,
    ParsedEtymologyImporter,
    PronunciationImporter,
    ProverbImporter,
    ReferencesImporter,
    RelatedTermsImporter,
    RhymeImporter,
    SeeAlsoImporter,
    SynonymImporter,
    TranscriptionImporter,
    TroponymImporter,
    WikidataImporter,
    WikipediaImporter,
    _parse_wikicode,
    _pronunciation_line_parts_of_speech,
    wikicode_parse_session,
)
from . import ApiImporterTester


class TestFurtherReadingImporter(ApiImporterTester):
    Importer = FurtherReadingImporter
    data_exists_index = 0
    data_does_not_exist_index = None
    filename = "importers/further_reading.wiki"
    language = "fr"

    def test_corner_case(self):
        importer = self.Importer()
        data = importer.get_data(
            "", self.wikipages[self.data_exists_index], self.language
        )
        self.assertEqual(len(data), 1)


class TestAlternativeFormsImporter(ApiImporterTester):
    Importer = AlternativeFormsImporter
    data_exists_index = 0
    data_does_not_exist_index = None
    filename = "importers/alternative_forms.wiki"
    language = "pl"

    def test_get_data_check_equality(self):
        importer = self.Importer()
        data = importer.get_data("", self.wikipages[self.data_exists_index], "pl")
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0], "fi")


class TestAntonymImporter(ApiImporterTester):
    Importer = AntonymImporterL5
    data_exists_index = 6
    data_does_not_exist_index = 0
    filename = "importers/en-wikipage_references.txt"
    language = "vi"


class TestDerivedTermsImporter(ApiImporterTester):
    Importer = DerivedTermsImporter
    data_exists_index = 0
    data_does_not_exist_index = None
    filename = "importers/derived_terms.wiki"
    language = "vi"

    def test_specific_templates_are_resolved(self):
        importer = self.Importer()
        data = importer.get_data("", self.wikipages[self.data_exists_index], self.language)
        self.assertIn("phi báo", data)
        self.assertIn("phi hành gia", data)
        self.assertIn("phi trường", data)

    def test_template_list_items_are_parsed(self):
        importer = self.Importer()
        wikipage = (
            "==Vietnamese==\n"
            "====Derived terms====\n"
            "{{der-top|vi}}\n"
            "|phi báo\n"
            "|phi hành gia#note}}\n"
            "|[[phi trường]]\n"
            "}}\n\n"
        )
        data = importer.get_data("", wikipage, self.language)
        self.assertIn("phi báo", data)
        self.assertIn("phi hành gia", data)
        self.assertIn("phi trường", data)


class TestSeeAlsoImporter(ApiImporterTester):
    Importer = SeeAlsoImporter
    data_exists_index = 6
    data_does_not_exist_index = None
    filename = "importers/en-wikipage.txt"
    language = "vi"

    def test_template_links_resolved(self):
        importer = self.Importer()
        data = importer.get_data("", self.wikipages[self.data_exists_index], self.language)
        self.assertIn("phi-la-tốp", data)
        self.assertIn("phi lê", data)


class TestPronunciationImporter(ApiImporterTester):
    Importer = PronunciationImporter
    data_exists_index = 0
    data_does_not_exist_index = None
    filename = "importers/pronunciation.wiki"
    language = "ja"

    # def test_get_data_exists(self):
    #     pass


class TestReferencesImporter(ApiImporterTester):
    Importer = ReferencesImporter
    data_exists_index = 0
    data_does_not_exist_index = 2
    filename = "importers/en-wikipage_references.txt"
    language = "en"


class TestEtymologyImporter(ApiImporterTester):
    Importer = EtymologyImporter
    data_exists_index = 6
    data_does_not_exist_index = 1
    language = "vi"


class TestParsedEtymologyImporter(ApiImporterTester):
    Importer = ParsedEtymologyImporter
    data_exists_index = 0
    data_does_not_exist_index = None
    filename = "importers/parsed_etymology.wiki"
    language = "en"

    def test_parsed_content(self):
        importer = self.Importer()
        data = importer.get_data("", self.wikipages[0], self.language)
        expected = (
            "From {{enm}} ''þrusten'', from {{non}} ''þrysta'', "
            "from {{gem-pro}} ''*þrustijaną'', possibly from {{ine-pro}} ''*trewd-''. "
            "{{ine-pro}} ''*trewd-''."
        )
        self.assertEqual(data[0], expected)

    def test_numbered_sections_are_parsed(self):
        importer = self.Importer()
        wikipage = (
            "==English==\n"
            "===Etymology 1===\n"
            "From origin\n\n"
        )
        data = importer.get_data("", wikipage, self.language)
        self.assertEqual(data, ["From origin."])

    def test_parse_text_handles_render_failures_and_refs(self):
        importer = self.Importer()
        importer._render_template = (
            lambda template: (_ for _ in ()).throw(ValueError("boom"))
            if str(template.name).strip() == "bad"
            else "rendered"
        )
        parsed = importer._parse_text("From {{good}} <ref>note</ref> and {{bad}}")
        self.assertIn("rendered", parsed)
        self.assertIn("{{bad}}", parsed)
        self.assertNotIn("<ref>", parsed)
        self.assertTrue(parsed.endswith("."))


class TestSynonymImporter(ApiImporterTester):
    Importer = SynonymImporter
    data_exists_index = 6
    data_does_not_exist_index = 1
    language = "vi"


class TestHeadwordImporter(ApiImporterTester):
    Importer = HeadwordImporter
    data_exists_index = 3
    data_does_not_exist_index = 0
    language = "pl"

    def test_get_data_exists(self):
        pass


class TestTranscriptionImporter(ApiImporterTester):
    Importer = TranscriptionImporter
    data_exists_index = 3
    data_does_not_exist_index = 0
    language = "pl"

    def test_get_data_exists(self):
        pass


def test_repeated_sections_retain_order_and_pos_scope() -> None:
    """Read repeated headings fully without leaking relations across POS entries."""

    wikipage = """==English==
===Etymology 1===
====Noun====
=====Synonyms=====
* first

* second
====Verb====
=====Synonyms=====
* act
====Classifier====
=====Synonyms=====
* counter-word
===Etymology 10===
====Noun====
=====Synonyms 2=====
* third
==French==
===Noun===
====Synonyms====
* autre
"""

    importer = SynonymImporter()
    assert importer.get_data("", wikipage, "en", "ana") == [
        "first",
        "second",
        "third",
    ]
    assert importer.get_data("", wikipage, "en", "mat") == ["act"]


def test_inline_linkages_and_named_column_templates() -> None:
    """Extract direct sense templates and modern named-language columns."""

    wikipage = """==English==
===Noun===
# A companion. {{syn|en|ally|friend<q:informal>}}
====Synonyms====
* [[companion]]
====Derived terms====
{{col3|lang=en|allyship|friendship}}
"""

    assert SynonymImporter().get_data("", wikipage, "en", "ana") == [
        "ally",
        "friend",
        "companion",
    ]
    assert DerivedTermsImporter().get_data("", wikipage, "en", "ana") == [
        "allyship",
        "friendship",
    ]


def test_single_term_templates_preserve_order_and_ignore_display_data() -> None:
    """Treat display, transliteration, and gloss parameters as metadata."""

    wikipage = """==English==
===Noun===
====Synonyms====
* [[first]]
* {{l|en|second|display|transliteration|gloss}}
* [[third]]
"""
    assert SynonymImporter().get_data("", wikipage, "en", "ana") == [
        "first",
        "second",
        "third",
    ]


def test_all_flat_linkage_families_are_supported() -> None:
    """Expose every standard Wiktextract linkage family in the flat contract."""

    cases = [
        (RelatedTermsImporter, "Related terms"),
        (HypernymImporter, "Hypernyms"),
        (HyponymImporter, "Hyponyms"),
        (HolonymImporter, "Holonyms"),
        (MeronymImporter, "Meronyms"),
        (CoordinateTermsImporter, "Coordinate terms"),
        (TroponymImporter, "Troponyms"),
        (InstanceImporter, "Instances"),
        (ProverbImporter, "Proverbs"),
        (AbbreviationImporter, "Abbreviations"),
    ]
    for importer_class, heading in cases:
        wikipage = (
            "==English==\n===Noun===\n"
            f"===={heading}====\n* {{" + "{l|en|target}}\n"
        )
        assert importer_class().get_data("", wikipage, "en", "ana") == [
            "target"
        ]


def test_compounds_are_derived_terms() -> None:
    """Follow Wiktextract by folding Compounds into derived terms."""

    wikipage = """==English==
===Noun===
====Compounds====
* [[snowball]]
"""
    assert DerivedTermsImporter().get_data("", wikipage, "en", "ana") == [
        "snowball"
    ]


def test_descendants_accept_target_language_codes() -> None:
    """Flatten directly encoded descendants even when their languages differ."""

    wikipage = """==English==
===Descendants===
    * {{desc|fr|mot|romanization|gloss}}
** {{l|de|Wort}}
"""
    assert DescendantImporter().get_data("", wikipage, "en") == ["mot", "Wort"]


def test_recursive_descendants_preserve_hierarchy_and_direct_metadata() -> None:
    """Build Wiktextract-style trees from directly encoded list nesting."""

    wikipage = """==English==
===Noun===
====Descendants====
* Balkan Romance:
** {{desc|fr|mot<tr:mo><t:word>|motet<q:dated>|qq2=rare}}
*** {{desc|frm|motet|t=diminutive}}
* {{desc|de|Wort|tr=vort|t=word|bor=1}}
* {{desc|fr|mot}}
"""
    tree = DescendantImporter().get_tree_data("", wikipage, "en", "ana")
    assert tree == [
        {
            "lang": "Balkan Romance",
            "lang_code": "unknown",
            "descendants": [
                {
                    "lang": "French",
                    "lang_code": "fr",
                    "word": "mot",
                    "roman": "mo",
                    "sense": "word",
                    "descendants": [
                        {
                            "lang": "Middle French",
                            "lang_code": "frm",
                            "word": "motet",
                            "sense": "diminutive",
                        }
                    ],
                },
                {
                    "lang": "French",
                    "lang_code": "fr",
                    "word": "motet",
                    "tags": ["dated", "rare"],
                    "descendants": [
                        {
                            "lang": "Middle French",
                            "lang_code": "frm",
                            "word": "motet",
                            "sense": "diminutive",
                        }
                    ],
                },
            ],
        },
        {
            "lang": "German",
            "lang_code": "de",
            "word": "Wort",
            "roman": "vort",
            "sense": "word",
            "raw_tags": ["borrowed"],
        },
        {"lang": "French", "lang_code": "fr", "word": "mot"},
    ]
    first_children = tree[0]["descendants"]
    assert first_children[0]["descendants"][0] is not first_children[1][
        "descendants"
    ][0]


def test_recursive_descendants_parse_mixed_markers_and_skip_empty_intermediates() -> None:
    """Preserve full list-marker ancestry without shadowing valid parents."""

    wikipage = """==English==
===Noun===
====Descendants====
: {{desc|fr|racine}}
:# {{desc|de|Kind}}
:#* {{desc|nl|klein}}
* {{desc|es|raíz}}
** {{unsupported|group}}
*** {{desc|pt|raiz}}
*# {{desc|it|radice}}
*#* {{desc|ro|rădăcină}}
"""

    assert DescendantImporter().get_tree_data("", wikipage, "en", "ana") == [
        {
            "lang": "French",
            "lang_code": "fr",
            "word": "racine",
            "descendants": [
                {
                    "lang": "German",
                    "lang_code": "de",
                    "word": "Kind",
                    "descendants": [
                        {"lang": "Dutch", "lang_code": "nl", "word": "klein"}
                    ],
                }
            ],
        },
        {
            "lang": "Spanish",
            "lang_code": "es",
            "word": "raíz",
            "descendants": [
                {"lang": "Portuguese", "lang_code": "pt", "word": "raiz"},
                {
                    "lang": "Italian",
                    "lang_code": "it",
                    "word": "radice",
                    "descendants": [
                        {
                            "lang": "Romanian",
                            "lang_code": "ro",
                            "word": "rădăcină",
                        }
                    ],
                },
            ],
        },
    ]


def test_recursive_descendants_distinguish_plain_terms_from_groups() -> None:
    """Render plain terms as words and reserve unknown groups for parent rows."""

    wikipage = """==English==
===Descendants===
* finish
** {{desc|fr|finir}}
* New York
* rock and roll
* Tongic
** {{desc|to|tapu}}
"""

    assert DescendantImporter().get_tree_data("", wikipage, "en") == [
        {
            "lang": "unknown",
            "lang_code": "unknown",
            "word": "finish",
            "descendants": [
                {"lang": "French", "lang_code": "fr", "word": "finir"}
            ],
        },
        {"lang": "unknown", "lang_code": "unknown", "word": "New York"},
        {
            "lang": "unknown",
            "lang_code": "unknown",
            "word": "rock and roll",
        },
        {
            "lang": "Tongic",
            "lang_code": "unknown",
            "descendants": [
                {"lang": "Tongan", "lang_code": "to", "word": "tapu"}
            ],
        },
    ]


def test_recursive_descendants_support_direct_template_schemas() -> None:
    """Read unambiguous descendant, link, Japanese, and Chinese parameters."""

    wikipage = """==English==
===Noun===
====Descendants====
: {{desc|la-vul||alt=oricla|q=archaic|q1=rare|bor1=1}}
* {{desctree|fr|un|deux|alt2=deuxième|t2=second}}
* {{desc|pt|artelho<inh>|artigo<slb>|bor2=1}}
* {{l|de|Ziel|Anzeige|target}}
* {{ja-r|今|いま|gloss=now|rom=ima}}
* {{zh-l|圖書|túshū|books}}
* {{zh-l|中國|China}}
* {{zh-l|中國|中国|Zhōngguó|China|q=rare}}
* {{zh-l|臺灣/台灣/台湾|Táiwān|Taiwan}}
* {{desc|fr|one|2=two}}
"""

    assert DescendantImporter().get_tree_data("", wikipage, "en", "ana") == [
        {
            "lang": "unknown",
            "lang_code": "la-vul",
            "word": "oricla",
            "tags": ["archaic", "rare"],
            "raw_tags": ["borrowed"],
        },
        {"lang": "French", "lang_code": "fr", "word": "un"},
        {
            "lang": "French",
            "lang_code": "fr",
            "word": "deuxième",
            "sense": "second",
        },
        {
            "lang": "Portuguese",
            "lang_code": "pt",
            "word": "artelho",
            "raw_tags": ["inherited"],
        },
        {
            "lang": "Portuguese",
            "lang_code": "pt",
            "word": "artigo",
            "raw_tags": ["borrowed", "semi-learned borrowing"],
        },
        {
            "lang": "German",
            "lang_code": "de",
            "word": "Anzeige",
            "sense": "target",
        },
        {
            "lang": "Japanese",
            "lang_code": "ja",
            "word": "今",
            "roman": "ima",
            "sense": "now",
        },
        {
            "lang": "Chinese",
            "lang_code": "zh",
            "word": "圖書",
            "roman": "túshū",
            "sense": "books",
        },
        {"lang": "Chinese", "lang_code": "zh", "word": "中國"},
        {
            "lang": "Chinese",
            "lang_code": "zh",
            "word": "中國",
            "roman": "Zhōngguó",
            "sense": "China",
            "tags": ["rare", "Traditional-Chinese"],
        },
        {
            "lang": "Chinese",
            "lang_code": "zh",
            "word": "中国",
            "roman": "Zhōngguó",
            "sense": "China",
            "tags": ["rare", "Simplified-Chinese"],
        },
        {
            "lang": "Chinese",
            "lang_code": "zh",
            "word": "臺灣",
            "roman": "Táiwān",
            "sense": "Taiwan",
        },
        {
            "lang": "Chinese",
            "lang_code": "zh",
            "word": "台灣",
            "roman": "Táiwān",
            "sense": "Taiwan",
        },
        {
            "lang": "Chinese",
            "lang_code": "zh",
            "word": "台湾",
            "roman": "Táiwān",
            "sense": "Taiwan",
        },
        {"lang": "French", "lang_code": "fr", "word": "two"},
    ]


def test_recursive_descendants_bound_tree_depth_and_size() -> None:
    """Keep preview serialization below Python and browser recursion limits."""

    deep_lines = [
        f"{'*' * depth} {{{{desc|fr|mot-{depth}}}}}" for depth in range(1, 40)
    ]
    wide_lines = [f"* {{{{desc|fr|mot-{index}}}}}" for index in range(2_005)]
    wikipage = "==English==\n===Descendants===\n" + "\n".join(
        [*deep_lines, *wide_lines]
    )

    tree = DescendantImporter().get_tree_data("", wikipage, "en")
    pending = list(tree)
    node_count = 0
    max_depth = 0
    pending_with_depth = [(node, 1) for node in pending]
    while pending_with_depth:
        node, depth = pending_with_depth.pop()
        node_count += 1
        max_depth = max(max_depth, depth)
        pending_with_depth.extend(
            (child, depth + 1) for child in node.get("descendants", [])
        )
    assert node_count == 2_000
    assert max_depth == 32

    template_terms = "|".join(f"mot-{index}" for index in range(2_005))
    template_page = (
        "==English==\n===Descendants===\n* {{desc|fr|"
        + template_terms
        + "}}"
    )
    assert len(DescendantImporter().get_tree_data("", template_page, "en")) == 2_000

    amplified_terms = "|".join(f"mot-{index}" for index in range(500))
    amplified_page = (
        "==English==\n===Descendants===\n* {{desc|fr|"
        + amplified_terms
        + "|q="
        + ("x" * 10_000)
        + "}}"
    )
    amplified_tree = DescendantImporter().get_tree_data("", amplified_page, "en")
    assert len(amplified_tree) == 500
    assert max(len(node["raw_tags"][0]) for node in amplified_tree) == 512
    assert len(json.dumps(amplified_tree).encode("utf-8")) < 1_000_000


def test_pronunciation_raw_lines_and_direct_atoms() -> None:
    """Capture direct pronunciation data that the old IPA-only filter dropped."""

    wikipage = """==English==
===Pronunciation===
* {{IPA|en|/fʊ/|[fuː]}}
* {{enPR|fo͝o}}
* {{audio|en|En-us-foo.ogg|Audio (US)}}
* {{hyph|en|ba|na|na}}
* {{rhymes|en|uː}}
* Homophone: [[fou]]
"""

    raw = PronunciationImporter().get_data("", wikipage, "en")
    assert "{{audio|en|En-us-foo.ogg|Audio (US)}}" in raw
    assert "{{rhymes|en|uː}}" in raw
    assert IPAImporter().get_data("", wikipage, "en") == ["/fʊ/", "[fuː]"]
    assert EnPRImporter().get_data("", wikipage, "en") == ["fo͝o"]
    assert AudioImporter().get_data("", wikipage, "en") == ["En-us-foo.ogg"]
    assert HyphenationImporter().get_data("", wikipage, "en") == ["ba-na-na"]
    assert RhymeImporter().get_data("", wikipage, "en") == ["uː"]
    assert HomophoneImporter().get_data("", wikipage, "en") == ["fou"]


def test_multiline_pronunciation_template_stays_one_entry() -> None:
    """Keep a pronunciation template spanning several lines as one entry."""

    wikipage = """==Chinese==
===Pronunciation===
{{zh-pron
|m=ròuyuán
|c=juk6 jyun4
|mn=tw,pn:bah-oân/ph:mah-îⁿ/ph:mah-oân
|mn-t=nêg8 in5
|w=sh:8gnioq yoe
|cat=n
}}

===Noun===
# a ball
"""

    raw = PronunciationImporter().get_data("", wikipage, "zho")
    assert raw == [
        "{{zh-pron\n"
        "|m=ròuyuán\n"
        "|c=juk6 jyun4\n"
        "|mn=tw,pn:bah-oân/ph:mah-îⁿ/ph:mah-oân\n"
        "|mn-t=nêg8 in5\n"
        "|w=sh:8gnioq yoe\n"
        "|cat=n\n"
        "}}"
    ]


def test_pronunciation_atoms_reject_mismatched_languages() -> None:
    """Do not turn foreign language-code parameters into sound values."""

    wikipage = """==English==
===Pronunciation===
* {{IPA|fr|/fu/}}
* {{audio|fr|French.ogg|Audio}}
* {{IPA|en|/fʊ/}}
* {{audio|en|English.ogg|Audio}}
"""
    assert IPAImporter().get_data("", wikipage, "en") == ["/fʊ/"]
    assert AudioImporter().get_data("", wikipage, "en") == ["English.ogg"]


def test_ipa_atoms_ignore_template_separators() -> None:
    """Do not turn IPA display punctuation into normalized pronunciations."""

    wikipage = """==English==
===Pronunciation===
* {{IPA|en|/a/|;|/b/}}
"""
    assert IPAImporter().get_data("", wikipage, "en") == ["/a/", "/b/"]


def test_pos_subsections_inside_pronunciation_are_scoped() -> None:
    """Read POS-labelled pronunciation subsections independently."""

    wikipage = """==English==
===Pronunciation===
====Noun====
* {{IPA|en|/naʊn/}}
====Verb====
* {{IPA|en|/vɜːb/}}
"""
    assert IPAImporter().get_data("", wikipage, "en", "ana") == ["/naʊn/"]
    assert IPAImporter().get_data("", wikipage, "en", "mat") == ["/vɜːb/"]


def test_inline_pronunciation_pos_labels_are_scoped() -> None:
    """Route textual and qualifier-template POS labels independently."""

    wikipage = """==English==
===Pronunciation===
* Noun: {{IPA|en|/naʊn/}}
* {{q|verb}} {{IPA|en|/vɜːb/}}
"""
    assert IPAImporter().get_data("", wikipage, "en", "ana") == ["/naʊn/"]
    assert IPAImporter().get_data("", wikipage, "en", "mat") == ["/vɜːb/"]


def test_multiple_hyphenations_and_plain_sound_lists() -> None:
    """Preserve alternate hyphenations and split plain sound lists."""

    wikipage = """==Italian==
===Pronunciation===
* {{hyphenation|it|quiè|to||qui|è|to}}
* Rhymes: a, b; c
* Homophones: foo, bar
"""
    assert HyphenationImporter().get_data("", wikipage, "it") == [
        "quiè-to",
        "qui-è-to",
    ]
    assert RhymeImporter().get_data("", wikipage, "it") == ["a", "b", "c"]
    assert HomophoneImporter().get_data("", wikipage, "it") == ["foo", "bar"]


def test_generic_headword_and_exact_transcription_parameter() -> None:
    """Accept generic heads while excluding pronunciation false positives."""

    wikipage = """==Japanese==
===Noun===
{{head|ja|noun|head=語|tr=go}}
{{ja-pron|語}}
"""

    assert HeadwordImporter().get_data("", wikipage, "ja", "ana") == [
        "{{head|ja|noun|head=語|tr=go}}"
    ]
    assert TranscriptionImporter().get_data("", wikipage, "ja", "ana") == [
        "go"
    ]


def test_multiline_headword_and_transcription() -> None:
    """Parse complete headword templates instead of individual source lines."""

    wikipage = """==Japanese==
===Noun===
{{head|ja|noun
|head=語
|tr=go
}}
"""
    headwords = HeadwordImporter().get_data("", wikipage, "ja", "ana")
    assert len(headwords) == 1
    assert "|tr=go" in headwords[0]
    assert TranscriptionImporter().get_data("", wikipage, "ja", "ana") == ["go"]


def test_explicit_wikimedia_and_literal_metadata() -> None:
    """Extract directly supplied identifiers, article targets, and meanings."""

    wikipage = """==English==
===Noun===
{{wikipedia|Example article}}
{{wikidata|Q42}}
{{wikidata|L123}}
{{zh-forms|lit=bright moon}}
# A definition.
"""

    assert WikipediaImporter().get_data("", wikipage, "en", "ana") == [
        "Example article"
    ]
    assert WikidataImporter().get_data("", wikipage, "en", "ana") == [
        "Q42",
        "L123",
    ]
    assert LiteralMeaningImporter().get_data("", wikipage, "en", "ana") == [
        "bright moon"
    ]
    assert WikipediaImporter().get_data(
        "Entry title",
        "==English==\n===Noun===\n{{wikipedia}}\n",
        "en",
        "ana",
    ) == ["Entry title"]


def test_literal_meaning_ignores_example_metadata() -> None:
    """Keep an example template's literal translation at example scope."""

    wikipage = """==English==
===Noun===
#: {{ux|en|source text|lit=example literal meaning}}
"""
    assert LiteralMeaningImporter().get_data("", wikipage, "en", "ana") == []


def test_unrendered_etymology_templates_are_preserved() -> None:
    """Never erase source information when no custom renderer exists."""

    wikipage = """==English==
===Etymology===
From {{unsupported-origin|en|source}}!
"""
    assert ParsedEtymologyImporter().get_data("", wikipage, "en") == [
        "From {{unsupported-origin|en|source}}!"
    ]


def test_mutating_importers_copy_shared_wikicode() -> None:
    """Keep canonical session parses unchanged after etymology and IPA cleanup."""

    etymology = "From {{m|enm|word}} <ref>note</ref>"
    pronunciation = "{{IPA|en|/wɜːd/}} {{audio|en|word.ogg|Audio}}"

    with wikicode_parse_session():
        etymology_code = _parse_wikicode(etymology)
        ParsedEtymologyImporter()._parse_text(etymology)
        assert str(etymology_code) == etymology

        pronunciation_code = _parse_wikicode(pronunciation)
        assert IPAImporter()._extract_from_section(pronunciation, "en") == [
            "/wɜːd/"
        ]
        assert str(pronunciation_code) == pronunciation
        assert AudioImporter()._extract_from_section(pronunciation, "en") == [
            "word.ogg"
        ]


def test_pronunciation_pos_label_cache_returns_immutable_values() -> None:
    """Reuse one immutable label result within an extraction operation."""

    line = "* {{q|noun|verb}} {{IPA|en|/word/}}"
    with wikicode_parse_session():
        labels = _pronunciation_line_parts_of_speech(line)
        assert labels is _pronunciation_line_parts_of_speech(line)
        assert labels == frozenset({"ana", "mat"})
