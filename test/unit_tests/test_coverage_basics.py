from xml.etree.ElementTree import tostring

import pytest

from api.entryprocessor.wiki.base import (
    WiktionaryProcessor,
    WiktionaryProcessorException,
    lang2code,
    stripwikitext,
)
from api.entryprocessor.wiki.mg import MGWiktionaryProcessor
from api.importer import AdditionalDataImporter
from api.importer.rakibolanamalagasy import (
    DictionaryImporter,
    RakibolanaMalagasyImporter,
)
from api.importer.wiktionary import TemplateImporter, WiktionaryAdditionalDataImporter
from api.importer.wiktionary import mg as mg_importers
from api.importer.wiktionary.fr import DerivedTermsImporter as FrenchDerivedTermsImporter
from api.importer.wiktionary.fr import ListSubsectionImporter as FrenchListSubsectionImporter
from api.importer.wiktionary.fr import ReferencesImporter as FrenchReferencesImporter
from api.parsers.functions.postprocessors import (
    arabic_postprocessor,
    latin_postprocessor,
    russian_postprocessor,
)
from api.serialisers import Builder
from api.serialisers.json import JSONBuilder, JSONBuilderError
from api.serialisers.word import Entry as EntrySerialiser
from api.serialisers.word import Translation as TranslationSerialiser
from api.serialisers.xml import XMLBuilder, XMLBuilderError


class DummyResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


class ChildBuilder(Builder):
    def serialise(self):
        return {"child": "value"}


class ChildXmlBuilder(Builder):
    def serialise(self):
        from xml.etree.ElementTree import Element

        child = Element("Child")
        value = Element("Value")
        value.text = "nested"
        child.append(value)
        return child


class DemoJsonBuilder(JSONBuilder):
    def __init__(self):
        super().__init__()
        self.child = ChildBuilder()
        self.mapping = {"key": "value"}
        self.string = "text"
        self.number = 3
        self.empty = None
        self.items = [ChildBuilder(), "literal"]
        self.mapped_variables = [
            ("child", "child"),
            ("mapping", "mapping"),
            ("string", "string"),
            ("number", "number"),
            ("empty", "empty"),
            ("items", "items"),
        ]


class DemoXmlBuilder(XMLBuilder):
    def __init__(self):
        super().__init__()
        self.xml_node = "Root"
        self.children = [ChildXmlBuilder()]
        self.child = ChildXmlBuilder()
        self.string = "text"
        self.number = 7
        self.mapping = {"key": ["value"], 5: [6], "nested": [{"inner": ["leaf"]}]}
        self.empty = None
        self.mapped_variables = [
            ("Children", "children"),
            ("ChildDirect", "child"),
            ("String", "string"),
            ("Number", "number"),
            ("Mapping", "mapping"),
            ("Empty", "empty"),
        ]


class DummyImporter(AdditionalDataImporter):
    data_type = "demo"

    def get_data(self, template_title: str, wikipage: str, language: str) -> list:
        return ["first", "second"]


class DummyProcessor(WiktionaryProcessor):
    @property
    def language(self):
        return "xx"


class DummyForm:
    def __init__(self, lemma):
        self.lemma = lemma


def test_json_builder_serialises_supported_values_and_errors():
    assert DemoJsonBuilder().serialise() == {
        "child": {"child": "value"},
        "mapping": {"key": "value"},
        "string": "text",
        "number": 3,
        "empty": None,
        "items": [{"child": "value"}, "literal"],
    }

    missing = DemoJsonBuilder()
    missing.mapped_variables = [("missing", "missing")]
    with pytest.raises(JSONBuilderError):
        missing.serialise()

    unsupported = DemoJsonBuilder()
    unsupported.bad = object()
    unsupported.mapped_variables = [("bad", "bad")]
    with pytest.raises(JSONBuilderError):
        unsupported.serialise()


def test_xml_builder_serialises_supported_values_and_errors():
    xml_text = tostring(DemoXmlBuilder().serialise()).decode()
    assert "<Root>" in xml_text
    assert "<String>text</String>" in xml_text
    assert "<Number>7</Number>" in xml_text
    assert "<Empty />" in xml_text
    assert "KeyValuePairs" in xml_text

    missing = DemoXmlBuilder()
    missing.mapped_variables = [("Missing", "missing")]
    with pytest.raises(XMLBuilderError):
        missing.serialise()

    unsupported = DemoXmlBuilder()
    unsupported.bad = object()
    unsupported.mapped_variables = [("Bad", "bad")]
    with pytest.raises(XMLBuilderError):
        unsupported.serialise()


def test_word_serialisers_cover_property_mapping():
    class EntryModel:
        entry = "word"
        part_of_speech = "ana"
        language = "mg"
        definitions = ["definition"]
        additional_data = {"source": "test"}
        references = ["ref"]

    class TranslationModel:
        word = "word"
        part_of_speech = "ana"
        language = "mg"
        definition = "definition"

    assert EntrySerialiser(EntryModel()).serialise()["entry"] == "word"
    assert EntrySerialiser(EntryModel()).references == ["ref"]
    assert TranslationSerialiser(TranslationModel()).serialise()["definition"] == "definition"


def test_additional_data_importer_offline_and_write_paths(mocker):
    importer = DummyImporter(dry_run=True)
    importer.set_languages({"English": "en", "Malagasy": "mg"})
    assert importer.languages["English"] == "en"
    assert importer.iso_codes["en"] == "English"
    assert importer.is_data_type_already_defined([{"data_type": "demo"}])

    get = mocker.patch(
        "api.importer.requests.get",
        side_effect=[
            DummyResponse([{"id": 42}]),
            DummyResponse([]),
            DummyResponse([{"word_id": 42, "information": "first", "type": "demo"}]),
            DummyResponse([]),
        ],
    )
    post = mocker.patch("api.importer.requests.post")

    assert not importer.additional_word_information_already_exists(42, "missing")
    importer.process_non_wikipage("word", "content", "mg")
    importer.write_additional_data(42, "")
    post.assert_not_called()
    assert get.call_count >= 2


def test_additional_data_importer_errors_and_online_mapper(mocker):
    importer = DummyImporter(dry_run=True)
    importer.word_id_cache[("word", "mg")] = 10
    importer.get_data = lambda template_title, content, language: "not-a-list"
    with pytest.raises(AssertionError):
        importer.process_non_wikipage("word", "content", "mg")

    mapper = DummyImporter(dry_run=True)
    mocker.patch(
        "api.importer.requests.get",
        return_value=DummyResponse([{"english_name": "Malagasy", "iso_code": "mg"}]),
    )
    mapper.online_fetch_default_languages_mapper()
    assert mapper.languages == {"Malagasy": "mg"}
    assert mapper.iso_codes == {"mg": "Malagasy"}


def test_dictionary_importer_and_rakibolana_paths(mocker):
    importer = DictionaryImporter(dry_run=True)
    mocker.patch(
        "api.importer.rakibolanamalagasy.requests.get",
        side_effect=[
            DummyResponse([{"word": "trano", "language": "mg", "part_of_speech": "ana", "id": 1}]),
            DummyResponse([{"word": "hazo", "language": "mg", "part_of_speech": "ana", "id": 2}]),
            DummyResponse([]),
        ],
    )
    importer.populate_cache("mg")
    assert importer.get_word_id("trano", "mg", "ana") == 1
    assert importer.get_word_id("hazo", "mg", "ana") == 2
    assert importer.http_get_word_id("missing", "mg", "ana") is None

    rakibolana = RakibolanaMalagasyImporter(dry_run=True)
    writes = []
    rakibolana.get_word_id = lambda title, language, pos: 9 if pos == "mat" else None
    rakibolana.write_additional_data = lambda word_id, additional_data: writes.append(
        (rakibolana.data_type, word_id, additional_data)
    )
    rakibolana.write_tif("mandeha", "mg", "derived")
    rakibolana.write_raw("mandeha", "mg", "raw")
    assert ("rakibolana/derived", 9, "derived") in writes
    assert ("rakibolana/raw", 9, "raw") in writes
    assert rakibolana.data_type == "rakibolana/definition"

    rakibolana.get_word_id = lambda title, language, pos: None
    rakibolana.write_tif("missing", "mg", "ignored")
    rakibolana.write_raw("missing", "mg", "ignored")
    assert rakibolana.get_data("title", "page", "mg") is None


def test_wiktionary_importer_helpers(mocker):
    template = TemplateImporter(dry_run=True)
    assert template.get_data("temp", "x {{temp|mg|value}} y\n{{other|mg|no}}", "mg") == ["value y"]

    importer = WiktionaryAdditionalDataImporter(dry_run=True)
    importer.process_non_wikipage = mocker.Mock(return_value="processed")

    class Page:
        def get(self):
            return "content"

        def title(self):
            return "Title"

    assert importer.process_wikipage(Page(), "mg") == "processed"
    importer.process_non_wikipage.assert_called_once_with("Title", "content", "mg")
    importer.run("Category:Root", wiktionary=None)


def test_malagasy_and_french_list_importers(mocker):
    mocker.patch(
        "api.importer.wiktionary.mg.SubsectionImporter.get_data",
        return_value=["* {{l|mg|trano}} * [[hazo]] * plain * [[Thesaurus:skip]]"],
    )
    assert set(mg_importers.ListSubsectionImporter(dry_run=True).get_data("x", "content", "mg")) == {
        "trano",
        "hazo",
        " plain ",
    }

    mocker.patch(
        "api.importer.wiktionary.fr.SubsectionImporter.get_data",
        return_value=["* one * two"],
    )
    assert set(FrenchListSubsectionImporter(dry_run=True).get_data("x", "content", "fr")) == {" one ", " two"}

    mocker.patch(
        "api.importer.wiktionary.fr.SubsectionImporter.get_data",
        return_value=["* ref one\nref two"],
    )
    assert FrenchReferencesImporter(dry_run=True).get_data("x", "content", "fr") == ["ref one", "ref two"]

    mocker.patch(
        "api.importer.wiktionary.fr.SubsectionImporter.get_data",
        return_value=[
            "* {{l|fr|maison}} * [[arbre]] * [[Thesaurus:skip]]",
            "{{der3|fr\n|chien#note\n|chat}}",
        ],
    )
    assert set(FrenchDerivedTermsImporter(dry_run=True).get_data("x", "content", "fr")) == {
        "maison",
        "arbre",
        "chien",
        "chat",
    }


def test_base_processor_and_malagasy_processor(mocker, tmp_path):
    processor = DummyProcessor()
    processor.set_title("Local title")
    assert processor.title == "Local title"
    processor.set_text("text")
    processor.process()
    assert processor.content == "text"
    assert processor.advanced_extract_definition("ana", "definition") == "definition"
    assert processor.refine_definition("definition") == ["definition"]

    with pytest.raises(NotImplementedError):
        processor.retrieve_translations()
    with pytest.raises(NotImplementedError):
        processor.get_all_entries()

    no_page = DummyProcessor()
    with pytest.raises(WiktionaryProcessorException):
        no_page.process()

    class SyntaxPage:
        def get(self):
            raise SyntaxError("bad")

        def title(self):
            return "Page title"

    syntax_processor = DummyProcessor()
    syntax_processor.process(SyntaxPage())
    assert syntax_processor.content == ""
    assert syntax_processor.title == "Page title"

    assert stripwikitext(" [[shown|hidden]]. {{template}} [x] ") == "shownx"

    lang_file = tmp_path / "languagecodes.dct"
    lang_file.write_text("{'Malagasy': 'mg'}")
    mocker.patch("api.entryprocessor.wiki.base.data_file", f"{tmp_path}/")
    assert lang2code("Malagasy") == "mg"

    mg_processor = MGWiktionaryProcessor()
    mg_processor.title = "trano"
    mg_processor.set_text("{{-ana-|mg}}\n# [[house|trano]].\n# {{ignored}}\n=={{=fr=}}==")
    entries = mg_processor.get_all_entries()
    assert len(entries) == 1
    assert entries[0].entry == "trano"
    assert entries[0].language == "mg"
    assert entries[0].definitions == ["house"]
    assert mg_processor.retrieve_translations() == []
    assert MGWiktionaryProcessor().get_all_entries() == []


def test_parser_postprocessors():
    assert latin_postprocessor(DummyForm("amāre ē ī ō ū")).lemma == "amare e i o u"
    assert arabic_postprocessor(DummyForm("كَتَبَ")).lemma == "كتب"
    assert russian_postprocessor(DummyForm("мо́ре")).lemma == "море"


def test_xml_and_json_error_branches_for_iterables():
    class BadSerialise:
        message = "bad"

        def serialise(self):
            raise RuntimeError("bad")

    builder = DemoJsonBuilder()
    builder.items = [BadSerialise()]
    builder.mapped_variables = [("items", "items")]
    with pytest.raises(JSONBuilderError):
        builder.serialise()

    class NonDictSerialise:
        def serialise(self):
            return ["not", "dict"]

    builder.items = [NonDictSerialise()]
    with pytest.raises(JSONBuilderError):
        builder.serialise()

    xml_builder = DemoXmlBuilder()
    xml_builder.children = [object()]
    xml_builder.mapped_variables = [("Children", "children")]
    with pytest.raises(XMLBuilderError):
        xml_builder.serialise()
