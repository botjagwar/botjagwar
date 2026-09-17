# coding: utf8
import asyncio
import logging
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import pywikibot

from api import entryprocessor
from api.config import BotjagwarConfig
from api.decorator import catch_exceptions
from api.entryprocessor.wiki.base import WiktionaryProcessorException
from api.model.word import Entry
from api.output import Output
from api.servicemanager import DictionaryServiceManager
from redis_wikicache import NoPage, RedisPage as Page, RedisSite as Site
from .exceptions import TranslatedPagePushError, TranslationError
from .functions import postprocessors  # do __NOT__ delete!
from .processor_config import (
    ProcessorConfigManager,
    ProcessorConfigurationError,
    ProcessorType,
)

# from .functions import translate_using_postgrest_json_dictionary
# from .functions import translate_using_suggested_translations_fr_mg
# from .functions import translate_using_bridge_language
# from .functions import translate_form_of_templates
from .functions.definitions.rule_based import FormOfDefinitionTranslatorFactory

# from .functions import translate_using_convergent_definition
from .functions.definitions import translate_using_nllb
from .functions.etymology import translate_etymologies
from .functions.pronunciation import translate_pronunciation
from .functions.references import translate_references
from .functions.utils import filter_additional_data
from api.translation_v2.functions.definitions.language_model_based import whitelists

from .publishers import WiktionaryDirectPublisher
from .types import TranslatedDefinition

log = logging.getLogger(__name__)
URL_HEAD = DictionaryServiceManager().get_url_head()

translate_form_of_definitions = FormOfDefinitionTranslatorFactory('en').translate_form_of_templates
translation_methods = [
    # function + whether the definition must be refined.
    (translate_form_of_definitions,
     False,
     postprocessors.change_part_of_speech({
        "ana": "e-ana",
        "mpam": "e-mpam",
        "mat": "e-mat"
     })),

    (translate_using_nllb, True, None),
]

already_visited = []


@dataclass
class TranslationPageResult:
    """Result returned after processing a Wiktionary page."""

    title: str
    language: str
    status: str
    message: str
    entries_count: int = 0
    published: bool = False
    error_type: Optional[str] = None

    def serialise(self) -> Dict[str, Any]:
        """Return a JSON-serialisable representation of the result."""
        return asdict(self)


class Translation:
    working_wiki_language = "mg"

    def __init__(
        self,
        use_configured_postprocessors: bool = True,
        basic_english_gate_enabled: Optional[Callable[[], bool]] = None,
        nllb_roundtrip_validation_enabled: Optional[Callable[[], bool]] = None,
    ) -> None:
        """
        Translates entries into Malagasy. Other languages might be translated but such has not been
        attempted as of current. Translations methods are handled with separate functions.

        :param use_configured_postprocessors: Use the configuration file to configure postprocessors.
        Allows postprocessors to be defines on a per-language basis, or a language + part of speech basis.
        """
        super(Translation, self).__init__()

        self.single_definition_whitelist_length = 20000
        self.whitelists = {}
        for language, word_list in whitelists.items():
            if len(word_list) > self.single_definition_whitelist_length:
                self.whitelists[language] = set(word_list[:self.single_definition_whitelist_length])
            else:
                self.whitelists[language] = set(word_list)

        self.output = Output()
        self.default_publisher = WiktionaryDirectPublisher()
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        self.config = BotjagwarConfig()
        self._basic_english_gate_enabled = basic_english_gate_enabled or (lambda: False)
        self._nllb_roundtrip_validation_enabled = (
            nllb_roundtrip_validation_enabled or (lambda: True)
        )
        self.processor_config = ProcessorConfigManager()
        self._processor_modules = [postprocessors]
        if not use_configured_postprocessors:
            self._post_processors = []
            self.static_postprocessors = True
        else:
            self.static_postprocessors = False

    @property
    def post_processors(self):
        return self._post_processors

    def set_postprocessors(self, postprocessor_list: List[Callable]):
        self._post_processors = postprocessor_list
        self.static_postprocessors = True

    def load_processors(
        self, language: str, part_of_speech: Optional[str], processor_type: str
    ):
        """Return configured processors for the provided entry."""

        return self.processor_config.get_definitions(language, part_of_speech, processor_type)

    def _save_translation_from_page(self, infos: List[Entry]):
        """
        Update database and translation methods
        """
        for info in infos:
            self.output.db(info)
            self.output.add_translation_method(info)

    def publish_translated_references(
        self,
        reference_templates: Set[Tuple[str, str]],
        source_wiki: str = "en",
        target_wiki: str = "mg",
    ) -> None:
        """Publish reference templates collected for one translation job."""
        publish = self.default_publisher.publish_translated_references(
            self, reference_templates
        )
        publish(source_wiki, target_wiki)

    @staticmethod
    def add_wiktionary_credit(
        entries: List[Entry], wiki_page: entryprocessor.WiktionaryProcessor
    ) -> List[Entry]:
        reference = "{{wikibolana|" + wiki_page.language + "|" + wiki_page.title + "}}"
        out_entries = []
        for entry in entries:
            entry.origin_wiktionary = wiki_page.language
            if entry.additional_data is None:
                entry.additional_data = {}

            if "reference" in entry.additional_data:
                if isinstance(entry.additional_data["reference"], list):
                    entry.additional_data["reference"].append(reference)
                else:
                    entry.additional_data["reference"] = [reference]
            else:
                entry.additional_data["reference"] = [reference]

            out_entries.append(entry)
        return out_entries

    @staticmethod
    def _generate_summary_from_added_entries(entries: List[Entry]):
        return "Dikanteny: " + ", ".join(
            sorted(list({f"{entry.language.lower()}" for entry in entries}))
        )

    def check_if_page_exists(self, lemma):
        page = Page(
            Site(self.working_wiki_language, "wiktionary"), lemma, offline=False
        )
        return page.exists()

    def run_postprocessors(self, entries):
        """
        Apply configured postprocessors to the provided entries.

        Args:
            entries: List of Entry objects to process

        Returns:
            List of processed Entry objects
        """
        if self.static_postprocessors:
            return self._run_static_postprocessors(entries)
        else:
            return self._run_dynamic_processors(entries, ProcessorType.AFTER_TRANSLATION)

    def run_preprocessors(self, entry: Entry) -> List[Entry]:
        """Apply configured preprocessors on the provided entry."""

        if self.static_postprocessors:
            return [entry]

        processed = self._run_dynamic_processors([entry], ProcessorType.BEFORE_TRANSLATION)
        return processed

    def _check_processor_output(self, entries):
        """Validate that postprocessor output is correctly formatted."""
        if not isinstance(entries, list):
            raise TranslationError("Post-processors must return list")

        for entry in entries:
            if not isinstance(entry, Entry):
                raise TranslationError('Post-processors return list elements must all be of type Entry')

        return entries

    def _run_static_postprocessors(self, entries):
        """Run manually configured postprocessors in code."""
        if not isinstance(self.post_processors, list):
            raise TranslationError(f"post processor must be a list, not {self.post_processors.__class__}")

        if not self.post_processors:
            return entries

        processed_entries = entries
        for post_processor in self.post_processors:
            processed_entries = post_processor(processed_entries)

        return self._check_processor_output(processed_entries)

    def _run_dynamic_processors(self, entries: List[Entry], processor_type: str):
        """Run processors configured through configuration files."""

        result_entries: List[Entry] = []

        for entry in entries:
            definitions = self.load_processors(entry.language, entry.part_of_speech, processor_type)

            if not definitions:
                result_entries.append(entry)
                continue

            entry_to_process: List[Entry] = [entry]
            for definition in definitions:
                try:
                    processor_callable, resolved_arguments = self.processor_config.instantiate_processor(
                        definition, entry, self._processor_modules
                    )
                except ProcessorConfigurationError as exc:
                    log.error(
                        "Failed to instantiate processor '%s': %s",
                        definition.function_name,
                        exc,
                    )
                    raise

                log.debug(
                    "Running %s processor %s with arguments %s",
                    processor_type,
                    definition.function_name,
                    resolved_arguments,
                )

                entry_to_process = processor_callable(entry_to_process)
                entry_to_process = self._check_processor_output(entry_to_process)

            result_entries.extend(entry_to_process)

        return result_entries

    @staticmethod
    def aggregate_entry_data(
        entries_translated: List[Entry], entries_already_existing: List[Entry]
    ) -> List[Entry]:
        aggregated_entries = []
        for translated in entries_translated:
            aggregated_entries.extend(
                existing.overlay(translated)
                for existing in entries_already_existing
                if (
                    existing.language == translated.language
                    and existing.part_of_speech == translated.part_of_speech
                )
            )
                # if translated not in aggregated_entries:
                #     aggregated_entries.append(translated)

        return aggregated_entries

    def generate_summary(self, entries, target_page, content, force_ninja=False):
        if force_ninja or self.config.get("ninja_mode", "translator") == "1":
            if target_page.exists():
                summary = "nanitsy"
                if not target_page.isRedirectPage():
                    old_content = target_page.get()
                    if len(content) > len(old_content) * 1.25:
                        summary = "nanitatra"
            elif len(content) > 200:
                summary = f"Pejy noforonina tamin'ny « {content[:200]}... »"
            else:
                summary = f"Pejy noforonina tamin'ny « {content} »"
        else:
            summary = self._generate_summary_from_added_entries(entries)

        return summary

    def create_lemma_if_not_exists(self, wiktionary_processor, definitions, entry):
        if hasattr(definitions, "part_of_speech") and definitions.part_of_speech is not None:
            entry.part_of_speech = definitions.part_of_speech

        if (
            hasattr(definitions, "lemma")
            and definitions.lemma is not None
            and definitions.lemma not in already_visited
        ):
            already_visited.append(definitions.lemma)
            if not self.check_if_page_exists(definitions.lemma):
                log.debug(f"lemma {definitions.lemma} does not exist. Processing...")
                page = Page(
                    Site(wiktionary_processor.language, "wiktionary"), definitions.lemma
                )

                if page.exists():
                    self.process_wiktionary_wiki_page(page)

    @catch_exceptions(pywikibot.exceptions.InvalidTitleError)
    def create_or_rename_template_on_target_wiki(
        self,
        *,
        source_language: str,
        source_name: str,
        target_language: str,
        target_name: str,
    ) -> None:
        """Import a referenced template and create its translated-name redirect."""
        if target_language != "mg" or target_language != self.working_wiki_language:
            raise TranslatedPagePushError(
                "Template publication is restricted to Malagasy Wiktionary."
            )
        source_template_name = self._extract_template_name(source_name)
        target_template_name = self._extract_template_name(target_name)
        source_wiki = Site(source_language, "wiktionary")
        target_wiki = Site(target_language, "wiktionary")
        source_page = Page(source_wiki, "Template:" + source_template_name)
        redirect_target_page = (
            Page(target_wiki, "Endrika:" + source_template_name)
            if source_template_name != target_template_name
            else None
        )
        target_page = Page(target_wiki, "Endrika:" + target_template_name)
        if source_page.exists() and not source_page.isRedirectPage():
            content = source_page.get()
            if not target_page.exists():

                log.debug(f"Creating page for {target_page.title()}")
                log.debug(f"  Language: {target_page.site.lang}")

                target_page.put(
                    content,
                    (
                        f"Pejy noforonina tamin'ny « {content[:147]}... »"
                        if len(content) > 149
                        else f"Pejy noforonina tamin'ny « {content} »"
                    ),
                )
                log.info(
                    f"Template {source_page.title()} already exists at {target_wiki.wiki} wiki."
                )

            if redirect_target_page is not None and not redirect_target_page.exists():
                log.debug(f"Creating redirect page for {target_page.title()}")
                log.debug(f"  Language: {target_page.site.lang}")

                redirect_target_page.put(
                    f"#FIHODINANA [[{target_page.title()}]]", "mametra-pihodinana"
                )

    @staticmethod
    def _extract_template_name(template_call: str) -> str:
        """Return a bare template name from a name or full template invocation."""
        template_name = template_call.strip()
        if template_name.startswith("{{"):
            template_name = template_name[2:]
            delimiters = [
                position
                for position in (template_name.find("|"), template_name.find("}}"))
                if position >= 0
            ]
            if delimiters:
                template_name = template_name[: min(delimiters)]

        template_name = template_name.strip()
        for namespace in ("Template:", "Endrika:"):
            if template_name.casefold().startswith(namespace.casefold()):
                return template_name[len(namespace) :].strip()
        return template_name

    def get_single_word_definitions(
        self, definition: str, language: str, part_of_speech: str | None
    ) -> List[str]:
        """Get single-word definitions from an existing Wiktionary page."""
        ret = []

        if '[' in definition or ']' in definition:
            definition = definition.replace('[', '').replace(']', '')
        if '{' in definition or '}' in definition:
            definition = definition.replace('{', '').replace('}', '')

        page = Page(Site(language, "wiktionary"), definition)
        if not page.exists():
            log.debug(
                "Skipping dictionary expansion for %r because the %s Wiktionary page does not exist.",
                definition,
                language,
            )
            return []

        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(
            language
        )
        wiktionary_processor = wiktionary_processor_class()
        try:
            wiktionary_processor.process(page)
        except NoPage:
            log.debug(
                "Skipping dictionary expansion for %r because its page disappeared before processing.",
                definition,
            )
            return []

        for entry in wiktionary_processor.get_all_entries(
            get_additional_data=True, cleanup_definitions=True, advanced=True
        ):
            if entry.part_of_speech == part_of_speech and entry.language == language:
                for definition_line in entry.definitions:
                    try:
                        refined_definition_lines = wiktionary_processor.refine_definition(
                            definition_line, part_of_speech=entry.part_of_speech,
                            remove_all_templates=True,
                            drop_labels=["obsolete", "dated", "archaic", "slang", "colloquial", "informal"]
                        )
                    except WiktionaryProcessorException:
                        continue
                    if refined_definition_lines:
                        ret.append(refined_definition_lines[0])


        return ret

    # python
    def translate_wiktionary_page(
        self,
        wiktionary_processor: entryprocessor.WiktionaryProcessor,
        reference_templates: Optional[Set[Tuple[str, str]]] = None,
    ) -> List[Entry]:
        """
        Parse Wiktionary page data and translate any content/section that can be translated.
        """
        if reference_templates is None:
            reference_templates = set()

        entries = wiktionary_processor.get_all_entries(
            get_additional_data=True,
            translate_definitions_to_malagasy=True,
            human_readable_form_of_definition=True,
        )
        translated_entries = []

        for entry in entries:
            entries_to_translate = self.run_preprocessors(entry)
            for preprocessed_entry in entries_to_translate:
                translated_definitions = self._translate_entry_definitions(
                    preprocessed_entry, wiktionary_processor
                )
                if translated_definitions:
                    translated_entry = self._prepare_translated_entry(
                        preprocessed_entry,
                        translated_definitions,
                        wiktionary_processor,
                        reference_templates,
                    )
                    translated_entries.append(translated_entry)

        translated_entries = self._postprocess_entries(translated_entries, wiktionary_processor)
        return translated_entries

    def _translate_entry_definitions(self, entry: Entry, wiktionary_processor) -> List[str]:
        """
        Translate definitions for a single entry using available translation methods.
        """
        translated_definitions = []
        for definition_line in entry.definitions:
            refined_definitions = self._refine_definitions(definition_line, entry, wiktionary_processor)
            cleaned_definitions = []
            for refined_definition in refined_definitions:
                refined_definition_size = len(refined_definition.split())
                if refined_definition_size < 2 and refined_definition not in self.whitelists[wiktionary_processor.language]:
                    try:
                        cleaned_definitions += self.get_single_word_definitions(refined_definition, wiktionary_processor.language, entry.part_of_speech)
                    except pywikibot.exceptions.InvalidTitleError:
                        # If the definition is not a valid title, skip it
                        continue
                else:
                    cleaned_definitions += [refined_definition]

            for refined_definition in cleaned_definitions:
                translation = self._apply_translation_methods(refined_definition, entry, wiktionary_processor)
                if translation:
                    translated_definitions.append(translation)

        return list(dict.fromkeys(translated_definitions))  # Remove duplicates without changing definition order

    def _refine_definitions(self, definition_line: str, entry: Entry, wiktionary_processor) -> List[str]:
        """
        Refine a definition line for translation.
        """
        try:
            return wiktionary_processor.refine_definition(
                definition_line, part_of_speech=entry.part_of_speech
            )
        except WiktionaryProcessorException:
            return []

    def _apply_translation_methods(self, definition: str, entry: Entry, wiktionary_processor) -> Optional[str]:
        """
        Apply translation methods to a single definition.
        """
        for translation_method, refine_function, post_translation_postprocessor in translation_methods:
            if refine_function:
                definition = self._remove_templates(definition, entry, wiktionary_processor)

            if definition:
                translation = translation_method(
                    entry,
                    definition,
                    wiktionary_processor.language,
                    self.working_wiki_language,
                    language=entry.language,
                    basic_english_gate_enabled=self._basic_english_gate_enabled,
                    nllb_roundtrip_validation_enabled=(
                        self._nllb_roundtrip_validation_enabled
                    ),
                )
                if isinstance(translation, TranslatedDefinition):
                    if post_translation_postprocessor:
                        # The side effect is to change the contents of the entry
                        # into the correct one.
                        post_translation_postprocessor([entry])
                    return str(translation)

        return None

    def _remove_templates(self, definition: str, entry: Entry, wiktionary_processor) -> str:
        """
        Remove templates from a definition if required by the translation method.
        """
        if definition and isinstance(definition, list):
            definition = definition[0]
        refined = wiktionary_processor.refine_definition(
            definition, part_of_speech=entry.part_of_speech, remove_all_templates=True
        )
        return refined[0] if refined else ''

    def _prepare_translated_entry(
        self,
        entry: Entry,
        definitions: List[str],
        wiktionary_processor,
        reference_templates: Optional[Set[Tuple[str, str]]] = None,
    ) -> Entry:
        """
        Prepare a translated entry with additional data and references.
        """
        translated_entry = deepcopy(entry)
        translated_entry.definitions = definitions
        translated_entry.additional_data = self._translate_additional_data(
            translated_entry, wiktionary_processor, reference_templates
        )
        return translated_entry

    def _translate_additional_data(
        self,
        entry: Entry,
        wiktionary_processor,
        reference_templates: Optional[Set[Tuple[str, str]]] = None,
    ) -> dict:
        """
        Translate additional data such as references and pronunciation.
        """
        if reference_templates is None:
            reference_templates = set()
        additional_data = (
            dict(entry.additional_data)
            if isinstance(entry.additional_data, dict)
            else {}
        )
        if (
            "etymology" not in additional_data
            and wiktionary_processor.language == "en"
            and self.working_wiki_language == "mg"
            and isinstance(additional_data.get("etym/en"), list)
        ):
            translated_etymologies = translate_etymologies(
                additional_data["etym/en"],
                source=wiktionary_processor.language,
                target=self.working_wiki_language,
                translate_glosses=True,
            )
            if translated_etymologies:
                additional_data["etymology"] = translated_etymologies
        for reference_name in ("reference", "further_reading"):
            if reference_name not in additional_data:
                continue

            original_references = additional_data[reference_name]
            translated_references = translate_references(
                original_references,
                source=wiktionary_processor.language,
                target=self.working_wiki_language,
                use_postgrest="automatic",
            )
            additional_data[reference_name] = translated_references
            reference_templates.update(
                zip(original_references, translated_references)
            )
        if "pronunciation" in additional_data:
            additional_data["pronunciation"] = translate_pronunciation(
                additional_data["pronunciation"], target=self.working_wiki_language
            )
        return filter_additional_data(additional_data)

    def _postprocess_entries(self, entries: List[Entry], wiktionary_processor) -> List[Entry]:
        """
        Run postprocessors on the translated entries.
        """
        entries = Translation.add_wiktionary_credit(entries, wiktionary_processor)
        return self.run_postprocessors(entries)

    def process_wiktionary_wiki_page(
            self, wiki_page: Page, custom_publish_function=None
    ) -> TranslationPageResult:
        """
        Process a Wiktionary page and handle translations.
        """
        page_title = wiki_page.title()
        language = wiki_page.site.lang

        if custom_publish_function is None:
            publish = self.default_publisher.publish_to_wiktionary(self)
        else:
            publish = custom_publish_function

        if not wiki_page.namespace().content:
            log.warning(
                "Skipping page '%s' as it has no content namespace.", page_title
            )
            return TranslationPageResult(
                title=page_title,
                language=language,
                status="skipped",
                message="Page is not in a content namespace.",
            )

        try:
            wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(
                language
            )
            wiktionary_processor = wiktionary_processor_class()
        except Exception as exc:
            log.exception(
                "Failed to create WiktionaryProcessor for language '%s': %s",
                language,
                exc,
            )
            return TranslationPageResult(
                title=page_title,
                language=language,
                status="error",
                message="Failed to create Wiktionary processor.",
                error_type=type(exc).__name__,
            )

        if wiki_page.isRedirectPage():
            try:
                return self.process_wiktionary_wiki_page(
                    wiki_page.getRedirectTarget(),
                    custom_publish_function=custom_publish_function,
                )
            except pywikibot.exceptions.InvalidTitleError as exc:
                log.error(
                    "Invalid redirect target for page '%s': %s", page_title, exc
                )
                return TranslationPageResult(
                    title=page_title,
                    language=language,
                    status="error",
                    message="Invalid redirect target.",
                    error_type=type(exc).__name__,
                )

        try:
            wiktionary_processor.set_title(page_title)
            wiktionary_processor.set_text(wiki_page.get())
        except Exception as exc:
            log.exception(
                "Failed to set text or title for page '%s': %s", page_title, exc
            )
            return TranslationPageResult(
                title=page_title,
                language=language,
                status="error",
                message="Failed to load page text.",
                error_type=type(exc).__name__,
            )

        try:
            reference_templates: Set[Tuple[str, str]] = set()
            out_entries = self.translate_wiktionary_page(
                wiktionary_processor, reference_templates
            )
            if not out_entries:
                log.info("No entries translated for page '%s'.", page_title)
                return TranslationPageResult(
                    title=page_title,
                    language=language,
                    status="no_entries",
                    message="No entries were translated.",
                )

            ret = self.output.wikipages(out_entries)
            if ret:
                log.debug(
                    "Translated entries for page '%s': %s", page_title, out_entries
                )
                publication_accepted = publish(
                    page_title=page_title,
                    entries=out_entries,
                )
                if publication_accepted is False:
                    return TranslationPageResult(
                        title=page_title,
                        language=language,
                        status="filtered",
                        message="Translated entries were discarded before publication.",
                        entries_count=len(out_entries),
                        published=False,
                    )
                self._save_translation_from_page(out_entries)
                self.publish_translated_references(
                    reference_templates,
                    wiktionary_processor.language,
                    self.working_wiki_language,
                )
                return TranslationPageResult(
                    title=page_title,
                    language=language,
                    status="published",
                    message="Translated entries were published.",
                    entries_count=len(out_entries),
                    published=True,
                )

            return TranslationPageResult(
                title=page_title,
                language=language,
                status="no_output",
                message="Translated entries produced no page output.",
            )
        except TranslationError as exc:
            log.error("Translation error for page '%s': %s", page_title, exc)
            return TranslationPageResult(
                title=page_title,
                language=language,
                status="error",
                message=str(exc),
                error_type=type(exc).__name__,
            )
        except Exception as exc:
            log.exception(
                "Unexpected error while processing page '%s': %s", page_title, exc
            )
            return TranslationPageResult(
                title=page_title,
                language=language,
                status="error",
                message="Unexpected error while processing page.",
                error_type=type(exc).__name__,
            )
