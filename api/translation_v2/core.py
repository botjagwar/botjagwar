# coding: utf8
import asyncio
import logging
import time
from copy import deepcopy
from typing import List

from pywikibot import output

from api import entryprocessor
from api.config import BotjagwarConfig
from api.output import Output
from api.servicemanager import DictionaryServiceManager
from object_model.word import Entry
from redis_wikicache import RedisPage as Page, RedisSite as Site
from .functions import translate_form_of_templates
# from .functions import translate_using_bridge_language
from .functions import translate_using_convergent_definition
# from .functions import translate_using_postgrest_json_dictionary
from .types import \
    UntranslatedDefinition, \
    TranslatedDefinition

log = logging.getLogger(__name__)
URL_HEAD = DictionaryServiceManager().get_url_head()
translation_methods = [
    translate_using_convergent_definition,
    # translate_using_bridge_language,
    # translate_using_postgrest_json_dictionary,
    translate_form_of_templates
]

already_visited = []


class TranslatedPagePushError(Exception):
    pass


class Translation:
    working_wiki_language = 'mg'

    def __init__(self):
        """
        Translates pages into Malagasy
        """
        super(self.__class__, self).__init__()
        self.output = Output()
        self.loop = asyncio.get_event_loop()
        self.config = BotjagwarConfig()

    def _save_translation_from_page(self, infos: List[Entry]):
        """
        Update database and translation methods
        """
        for info in infos:
            self.output.db(info)
            self.output.add_translation_method(info)

    @staticmethod
    def add_wiktionary_credit(entries: List[Entry], wiki_page: Page) -> List[Entry]:
        reference = "{{wikibolana|" + wiki_page.site.language + '|' + wiki_page.title() + '}}'
        out_entries = []
        for entry in entries:
            if hasattr(entry, 'reference'):
                if isinstance(entry.reference, list):
                    entry.reference.append(reference)
                else:
                    entry.reference = [reference]
            else:
                entry.reference = [reference]

            out_entries.append(entry)
        return out_entries

    def generate_summary(self, entries: List[Entry]):
        summary = 'Dikanteny: '
        summary += ', '.join(sorted(list(set([f'{entry.language.lower()}' for entry in entries]))))
        return summary

    def check_if_page_exists(self, lemma):
        page = Page(Site(self.working_wiki_language, 'wiktionary'), lemma, offline=False)
        return page.exists()

    @staticmethod
    def aggregate_entry_data(entries_translated: List[Entry], entries_already_existing: List[Entry]) -> List[Entry]:
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
        # log.debug(self.output.wikipages(entries))

        if target_page.namespace().id != 0:
            raise TranslatedPagePushError(
                f'Attempted to push translated page to {target_page.namespace().custom_name} '
                f'namespace (ns:{target_page.namespace().id}). '
                f'Can only push to ns:0 (main namespace)'
            )
        elif target_page.isRedirectPage():
            pass
            target_page.put(self.output.wikipages(entries), self.generate_summary(entries))
        else:
            # Get entries to aggregate
            if target_page.exists():
                wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(self.working_wiki_language)
                wiktionary_processor = wiktionary_processor_class()
                wiktionary_processor.set_text(target_page.get())
                wiktionary_processor.set_title(page_title)
                already_present_entries = wiktionary_processor.getall()
                print(already_present_entries)
                print(entries)
                # entries = self.aggregate_entry_data(entries, already_present_entries)

            content = self.output.wikipages(entries)
            # Push aggregated content
            output('**** \03{yellow}' + target_page.title() + '\03{default} ****')
            output('\03{white}' + self.generate_summary(entries) + '\03{default}')
            output('\03{green}' + content + '\03{default}')
            output('\03{yellow}--------------\03{default}')
            if self.config.get('ninja_mode', 'translator') == '1':
                if target_page.exists():
                    summary = 'nanitsy'
                    if not target_page.isRedirectPage():
                        old_content = target_page.get()
                        if len(content) > len(old_content) * 1.25:
                            summary = 'nanitatra'
                else:
                    if len(content) > 140:
                        summary = "Pejy voaforona amin'ny « " + content[:137] + '... »'
                    else:
                        summary = "Pejy voaforona amin'ny « " + content + ' »'
            else:
                summary = self.generate_summary(entries)

            target_page.put(content, summary)
            if self.config.get('ninja_mode', 'translator') == '1':
                time.sleep(12)

    def translate_wiktionary_page(self, wiktionary_processor: entryprocessor.WiktionaryProcessor) -> List[Entry]:
        """
        Parse Wiktionary page data and translate any content/section that can be translated
        """
        entries = wiktionary_processor.getall(
            fetch_additional_data=True,
            translate_definitions_to_malagasy=True,
            human_readable_form_of_definition=True
        )
        out_entries = []
        for entry in entries:
            # log.debug(entry)
            translated_definition = []
            translated_from_definition = []
            out_translation_methods = {}
            for definition_line in entry.entry_definition:
                refined_definition_lines = wiktionary_processor.refine_definition(definition_line)
                for refined_definition_line in refined_definition_lines:
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
                        elif isinstance(definitions, TranslatedDefinition):
                            if hasattr(definitions, 'part_of_speech'):
                                if definitions.part_of_speech is not None:
                                    entry.part_of_speech = definitions.part_of_speech
                            if hasattr(definitions, 'lemma') and\
                                    definitions.lemma is not None and\
                                    definitions.lemma not in already_visited:
                                already_visited.append(definitions.lemma)
                                if not self.check_if_page_exists(definitions.lemma):
                                    log.debug(f'lemma {definitions.lemma} does not exist. Processing...')
                                    page = Page(Site(wiktionary_processor.language, 'wiktionary'), definitions.lemma)
                                    if page.exists():
                                        self.process_wiktionary_wiki_page(page)

                            for d in definitions.split(','):
                                translated_definition.append(d.strip())
                                if d in out_translation_methods:
                                    out_translation_methods[d].append(t_method.__name__)
                                else:
                                    out_translation_methods[d] = [t_method.__name__]

                            translated_definition += [k.strip() for k in definitions.split(',')]

                    translated_from_definition.append(refined_definition_line)

            entry_definitions = sorted(list(set(translated_definition)))
            out_entry = deepcopy(entry)
            out_entry.translated_from_definition = ', '.join(translated_from_definition)
            out_entry.entry_definition = entry_definitions
            out_entry.translated_from_language = wiktionary_processor.language
            out_entry.translation_methods = out_translation_methods
            if entry_definitions:
                out_entries.append(out_entry)

        out_entries.sort()
        return out_entries

    def process_wiktionary_wiki_page(self, wiki_page: Page):
        if wiki_page.isEmpty():
            return

        if not wiki_page.namespace().content:
            return

        if callable(wiki_page.site.language):
            language = wiki_page.site.language()
        else:
            language = wiki_page.site.language

        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(language)
        wiktionary_processor = wiktionary_processor_class()
        if not wiki_page.isRedirectPage():
            wiktionary_processor.set_text(wiki_page.get())
            wiktionary_processor.set_title(wiki_page.title())
        else:
            return self.process_wiktionary_wiki_page(wiki_page.getRedirectTarget())
        try:
            out_entries = self.translate_wiktionary_page(wiktionary_processor)
            out_entries = Translation.add_wiktionary_credit(out_entries, wiki_page)
            ret = self.output.wikipages(out_entries)
            if ret != '':
                log.debug('out_entries>' + str(out_entries))
                self.publish_to_wiktionary(wiki_page.title(), out_entries)
                self._save_translation_from_page(out_entries)
                return len(out_entries)
            else:
                return 0
        except Exception as exc:
            log.exception(exc)
            return -1
