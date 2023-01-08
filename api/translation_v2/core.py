# coding: utf8
import asyncio
import configparser
import logging
import time
from copy import deepcopy
from typing import List, Tuple, Any, Callable

import pywikibot

from api import entryprocessor
from api.config import BotjagwarConfig
from api.decorator import catch_exceptions
from api.model.word import Entry
from api.output import Output
from api.servicemanager import DictionaryServiceManager
from redis_wikicache import RedisPage as Page, RedisSite as Site
from .functions import postprocessors  # do __NOT__ delete!
from .functions import \
    translate_form_of_templates, \
    translate_form_of_definitions
from .functions import translate_using_convergent_definition
# from .functions import translate_using_bridge_language
from .functions.pronunciation import translate_pronunciation
from .functions.references import translate_references
from .functions.utils import form_of_part_of_speech_mapper
from .functions.utils import try_methods_until_translated
from .types import \
    UntranslatedDefinition, \
    TranslatedDefinition, \
    FormOfTranslaton

log = logging.getLogger(__name__)
URL_HEAD = DictionaryServiceManager().get_url_head()
translation_methods = [
    try_methods_until_translated(
        translate_using_convergent_definition,
        # translate_using_bridge_language,
        # translate_using_postgrest_json_dictionary,
        # translate_using_opus_mt,
        translate_form_of_templates,
        translate_form_of_definitions,
    ),
]

already_visited = []


class TranslationError(Exception):
    pass


class TranslatedPagePushError(TranslationError):
    pass


class Translation:
    working_wiki_language = 'mg'

    def __init__(self, use_configured_postprocessors: bool = True):
        """
        Translates entries into Malagasy. Other languages might be translated but such has not been
        attempted as of current. Translations methods are handled with separate functions.

        :param use_configured_postprocessors: Use the configuration file to configure postprocessors.
        Allows postprocessors to be defines on a per-language basis, or a language + part of speech basis.
        """
        super(Translation, self).__init__()
        self.output = Output()
        self.loop = asyncio.get_event_loop()
        self.config = BotjagwarConfig(name='entry_translator/postprocessors.ini')
        self.reference_template_queue = set()
        if not use_configured_postprocessors:
            self._post_processors = list()
            self.static_postprocessors = True
        else:
            self.static_postprocessors = False

    @property
    def post_processors(self):
        return self._post_processors

    def set_postprocessors(self, postprocessors: List[Callable]):
        self._post_processors = postprocessors
        self.static_postprocessors = True

    def load_postprocessors(self, language, part_of_speech) -> List[Tuple[Any, Tuple]]:
        """
        Load preprocessors for the specified language and combination of language:part-of-speech.
        :param language:
        :param part_of_speech:
        :return: list of function names along with their static arguments
        """
        post_processors = []
        pos_specific_section_name = f'{language}:{part_of_speech}'
        try:
            language_section_postprocessors = self.config.specific_config_parser.options(language)
        except configparser.NoSectionError:
            pass
        else:
            for postprocessor_name in language_section_postprocessors:
                arguments = tuple(self.config.specific_config_parser.get(
                    language, postprocessor_name).split(','))
                post_processors.append((postprocessor_name, arguments))

        try:
            pos_specific_section = self.config.specific_config_parser.options(pos_specific_section_name)
        except configparser.NoSectionError:
            pass
        else:
            for postprocessor_name in pos_specific_section:
                arguments = tuple(self.config.specific_config_parser.get(
                    pos_specific_section_name, postprocessor_name).split(','))
                post_processors.append((postprocessor_name, arguments))

        return post_processors

    def _save_translation_from_page(self, infos: List[Entry]):
        """
        Update database and translation methods
        """
        for info in infos:
            self.output.db(info)
            self.output.add_translation_method(info)

    def publish_translated_references(self, source_wiki='en', target_wiki='mg'):
        for original_reference, translated_reference in self.reference_template_queue:
            # Check if it is a template reference, or a plain-text one
            if translated_reference.startswith('{{') or original_reference.startswith('{{'):
                self.create_or_rename_template_on_target_wiki(
                    source_wiki, original_reference, target_wiki, translated_reference
                )

        self.reference_template_queue = set()

    @staticmethod
    def add_wiktionary_credit(
            entries: List[Entry],
            wiki_page: [pywikibot.Page, Page]) -> List[Entry]:
        reference = "{{wikibolana|" + wiki_page.site.lang + \
            '|' + wiki_page.title() + '}}'
        out_entries = []
        for entry in entries:
            if entry.additional_data is None:
                entry.additional_data = {}

            if 'reference' in entry.additional_data:
                if isinstance(entry.additional_data['reference'], list):
                    entry.additional_data['reference'].append(reference)
                else:
                    entry.additional_data['reference'] = [reference]
            else:
                entry.additional_data['reference'] = [reference]

            out_entries.append(entry)
        return out_entries

    @staticmethod
    def _generate_summary_from_added_entries(entries: List[Entry]):
        summary = 'Dikanteny: '
        summary += ', '.join(
            sorted(list(set([f'{entry.language.lower()}' for entry in entries]))))
        return summary

    def check_if_page_exists(self, lemma):
        page = Page(Site(self.working_wiki_language, 'wiktionary'), lemma, offline=False)
        return page.exists()

    def run_postprocessors(self, entries):
        def check_post_processor_output(out_entries):
            # Check post-processor hasn't changed output data format
            if not isinstance(out_entries, list):
                raise TranslationError(f'Post-processors must return list')
            for entry in out_entries:
                if not isinstance(entry, Entry):
                    raise TranslationError(
                        f'Post-processors return list elements '
                        f'must all be of type Entry'
                    )

        def run_static_postprocessors(out_entries, post_processors):
            """
            Static postprocessor, manually set in-code
            :param out_entries:
            :param post_processors:
            :return:
            """
            for post_processor in post_processors:
                out_entries = post_processor(out_entries)
            check_post_processor_output(out_entries)
            return out_entries

        def run_dynamic_postprocessors(entries):
            """
            Dunamic postprocessor, set in the configuration file and run
            :param entries:
            :return:
            """
            out_entries = []
            for entry in entries:
                loaded_postprocessors = self.load_postprocessors(entry.language, entry.part_of_speech)
                if loaded_postprocessors:
                    entry_to_process = [entry]
                    for post_processor_name, arguments in loaded_postprocessors:
                        log.debug(f'Running postprocessor {post_processor_name} with arguments {arguments}')
                        function = getattr(postprocessors, post_processor_name)(*arguments)
                        entry_to_process = function(entry_to_process)

                    out_entries += entry_to_process
                else:
                    out_entries += [entry]

            return out_entries

        if self.static_postprocessors:
            if isinstance(self.post_processors, list):
                if self.post_processors:
                    entries = run_static_postprocessors(entries, self.post_processors)
            else:
                raise TranslationError(f"post processor must be a list, not {self.post_processors.__class__}")
        else:
            entries = run_dynamic_postprocessors(entries)

        return entries

    @staticmethod
    def aggregate_entry_data(
            entries_translated: List[Entry],
            entries_already_existing: List[Entry]) -> List[Entry]:
        aggregated_entries = []
        for translated in entries_translated:
            for existing in entries_already_existing:
                # same spelling and language and part of speech
                if existing.language == translated.language and \
                        existing.part_of_speech == translated.part_of_speech:
                    aggregated_entries.append(existing.overlay(translated))
            # if translated not in aggregated_entries:
            #     aggregated_entries.append(translated)

        return aggregated_entries

    def publish_to_wiktionary(self, page_title: str, entries: List[Entry]):
        """
        Push translated data and if possible avoid any information loss
        on target wiki if information is not filled in
        """
        site = Site(self.working_wiki_language, 'wiktionary')
        target_page = Page(site, page_title, offline=False)

        if target_page.namespace().id != 0:
            raise TranslatedPagePushError(
                f'Attempted to push translated page to {target_page.namespace().custom_name} '
                f'namespace (ns:{target_page.namespace().id}). '
                f'Can only push to ns:0 (main namespace)')
        elif target_page.isRedirectPage():
            content = self.output.wikipages(entries)
            target_page.put(
                content,
                self.generate_summary(target_page, entries, content)
            )
        else:
            # Get entries to aggregate
            if target_page.exists():
                wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(
                    self.working_wiki_language)
                wiktionary_processor = wiktionary_processor_class()
                wiktionary_processor.set_text(target_page.get())
                wiktionary_processor.set_title(page_title)
                content = target_page.get()
                for entry in entries:
                    content = self.output.delete_section(entry.language, content)
            else:
                content = ""

            content = content.strip()
            content += '\n'
            content += self.output.wikipages(entries).strip()
            # Push aggregated content
            target_page.put(content, self.generate_summary(entries, target_page, content))
            if self.config.get('ninja_mode', 'translator') == '1':
                time.sleep(12)

    def generate_summary(self, entries, target_page, content):
        if self.config.get('ninja_mode', 'translator') == '1':
            if target_page.exists():
                summary = 'nanitsy'
                if not target_page.isRedirectPage():
                    old_content = target_page.get()
                    if len(content) > len(old_content) * 1.25:
                        summary = 'nanitatra'
            else:
                if len(content) > 140:
                    summary = "Pejy noforonina tamin'ny « " + \
                              content[:200] + '... »'
                else:
                    summary = "Pejy noforonina tamin'ny « " + content + ' »'
        else:
            summary = self._generate_summary_from_added_entries(entries)

        return summary

    def create_lemma_if_not_exists(self, wiktionary_processor, definitions, entry):
        if hasattr(definitions, 'part_of_speech'):
            if definitions.part_of_speech is not None:
                entry.part_of_speech = definitions.part_of_speech

        if hasattr(definitions, 'lemma') and \
            definitions.lemma is not None and \
            definitions.lemma not in already_visited:
            already_visited.append(definitions.lemma)
            if not self.check_if_page_exists(definitions.lemma):
                log.debug(f'lemma {definitions.lemma} does not exist. Processing...')
                page = Page(Site(wiktionary_processor.language, 'wiktionary'), definitions.lemma)

                if page.exists():
                    self.process_wiktionary_wiki_page(page)

    @catch_exceptions(pywikibot.exceptions.InvalidTitleError)
    def create_or_rename_template_on_target_wiki(self, source_language, source_name, target_language, target_name):
        source_wiki = Site(source_language, 'wiktionary')
        target_wiki = Site(target_language, 'wiktionary')
        source_page = Page(source_wiki, 'Template:' + source_name.replace('{{', '').replace('}}', ''))
        redirect_target_page = Page(target_wiki, 'Endrika:' + source_name.replace('{{', '').replace('}}', ''))
        target_page = Page(target_wiki, 'Endrika:' + target_name.replace('{{', '').replace('}}', ''))
        if source_page.exists() and not source_page.isRedirectPage():
            content = source_page.get()
            if not target_page.exists():
                target_page.put(
                    content,
                    "Pejy noforonina tamin'ny « " + content[:147] + '... »'
                    if len(content) > 149
                    else "Pejy noforonina tamin'ny « " + content + ' »'
                )
                log.info(f"Template {source_page.title()} already exists at {target_wiki.wiki} wiki.")

            if not redirect_target_page.exists():
                redirect_target_page.put(f'#FIHODINANA [[{target_page.title()}]]', 'mametra-pihodinana')

    def translate_wiktionary_page(self, wiktionary_processor: entryprocessor.WiktionaryProcessor) -> List[Entry]:
        """
        Parse Wiktionary page data and translate any content/section that can be translated
        """
        entries = wiktionary_processor.get_all_entries(
            get_additional_data=True,
            translate_definitions_to_malagasy=True,
            human_readable_form_of_definition=True
        )
        out_entries = []
        for entry in entries:
            translated_definition = []
            translated_from_definition = []
            out_translation_methods = {}
            for definition_line in entry.definitions:
                refined_definition_lines = wiktionary_processor.refine_definition(
                    definition_line)
                for refined_definition_line in refined_definition_lines:
                    # Try translation methods in succession.
                    # If one method produces something, skip the rest
                    for t_method in translation_methods:
                        if entry.part_of_speech is None:
                            continue
                        definitions = t_method(
                            entry.part_of_speech,
                            refined_definition_line,
                            wiktionary_processor.language,
                            self.working_wiki_language,
                            language=entry.language
                        )
                        if isinstance(definitions, UntranslatedDefinition):
                            continue
                        elif isinstance(definitions, TranslatedDefinition) or isinstance(definitions, FormOfTranslaton):
                            # Change POS to something more specific for form-of definitions
                            if isinstance(definitions, FormOfTranslaton):
                                if entry.part_of_speech in form_of_part_of_speech_mapper.keys():
                                    entry.part_of_speech = form_of_part_of_speech_mapper[entry.part_of_speech]

                            for d in definitions.split(','):
                                # translated_definition.append(d.strip())
                                if d in out_translation_methods:
                                    out_translation_methods[d].append(t_method.__name__)
                                else:
                                    out_translation_methods[d] = [t_method.__name__]

                            translated_definition += [str(definitions)]
                            # break

                    translated_from_definition.append(refined_definition_line)

            entry_definitions = sorted(list(set(translated_definition)))
            out_entry = deepcopy(entry)
            if not out_entry.additional_data:
                out_entry.additional_data = {}

            out_entry.definitions = entry_definitions
            for definition in out_entry.definitions:
                if 'translation_data' not in out_entry.additional_data:
                    out_entry.additional_data['translation_data'] = []

                translation_data = {
                    'definition': definition,
                    'language': wiktionary_processor.language,
                    'method': out_translation_methods[definition] if definition in out_translation_methods else None
                }
                out_entry.additional_data['translation_data'].append(translation_data)

            if entry.additional_data is not None:
                for reference_name in ['reference', 'further_reading']:
                    if reference_name in entry.additional_data:
                        references = entry.additional_data[reference_name]
                        translated_references = translate_references(
                            references,
                            source=wiktionary_processor.language,
                            target=self.working_wiki_language,
                            use_postgrest='automatic'
                        )
                        out_entry.additional_data[reference_name] = translated_references
                        for reference, translated_reference in list(zip(references, translated_references)):
                            self.reference_template_queue.add((reference, translated_reference))

            if entry.additional_data and 'pronunciation' in entry.additional_data:
                out_entry.additional_data['pronunciation'] = translate_pronunciation(
                    entry.additional_data['pronunciation'])

            if entry_definitions:
                out_entries.append(out_entry)

        out_entries.sort()
        # Post-processors takes the list of entries and returns the same.
        out_entries = self.run_postprocessors(out_entries)
        return out_entries

    def process_wiktionary_wiki_page(self, wiki_page: [Page, pywikibot.Page]):
        if not wiki_page.namespace().content:
            return

        language = wiki_page.site.lang

        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(
            language)
        wiktionary_processor = wiktionary_processor_class()
        if not wiki_page.isRedirectPage():
            wiktionary_processor.set_text(wiki_page.get())
            wiktionary_processor.set_title(wiki_page.title())
        else:
            return self.process_wiktionary_wiki_page(
                wiki_page.getRedirectTarget())
        try:
            out_entries = self.translate_wiktionary_page(wiktionary_processor)
            out_entries = Translation.add_wiktionary_credit(
                out_entries, wiki_page)
            ret = self.output.wikipages(out_entries)
            if ret != '':
                log.debug('out_entries>' + str(out_entries))
                self.publish_to_wiktionary(wiki_page.title(), out_entries)
                self._save_translation_from_page(out_entries)
                self.publish_translated_references(wiktionary_processor.language, self.working_wiki_language)
                return len(out_entries)

            return 0
        except Exception as exc:
            log.exception(exc)
