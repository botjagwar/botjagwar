# coding: utf8
import asyncio
import logging

import requests
from aiohttp import ClientSession

from api import entryprocessor
from api.exceptions import NoWordException
from api.output import Output
from api.servicemanager import DictionaryServiceManager
from database.exceptions.http import WordDoesNotExistException
from object_model.word import Entry

log = logging.getLogger(__name__)
default_data_file = '/opt/botjagwar/conf/entry_translator/'
CYRILLIC_ALPHABET_LANGUAGES = ['ru', 'uk', 'bg', 'be']
LANGUAGE_BLACKLIST = ['fr', 'en', 'sh', 'ar', 'de', 'zh']
URL_HEAD = DictionaryServiceManager().get_url_head()
WORKING_WIKI_LANGUAGE = 'mg'


class Translation:
    def __init__(self):
        """Mandika teny ary pejy @ teny malagasy"""
        super(self.__class__, self).__init__()
        self.output = Output()
        self.language_blacklist = LANGUAGE_BLACKLIST
        self.loop = asyncio.get_event_loop()

    def _save_translation_from_bridge_language(self, infos: Entry):
        # summary = "Dikan-teny avy amin'ny dikan-teny avy amin'i %s.wiktionary" % infos.origin_wiktionary_edition
        # summary += " (%s)" % get_version()
        # wikipage = self.output.wikipage(infos)
        # target_language_page = pwbot.Page(pwbot.Site(WORKING_WIKI_LANGUAGE, 'wiktionary'), infos.entry)
        # try:
        #     if target_language_page.exists():
        #         page_content = target_language_page.get()
        #         if page_content.find('{{=%s=}}' % infos.language) != -1:
        #             self.output.db(infos)
        #             return
        #         else:
        #             wikipage += page_content
        #             summary = "+" + summary
        # except pwbot.exceptions.IsRedirectPage:
        #     infos.entry = target_language_page.getRedirectTarget().title()
        #     self.output.db(infos)
        #     self._save_translation_from_bridge_language(infos)
        #     return
        #
        # except pwbot.exceptions.InvalidTitle as exc:
        #     log.exception(exc)
        #     return
        #
        # except Exception as exc:
        #     log.exception(exc)
        #     return
        #
        # target_language_page.put_async(wikipage, summary)
        self.output.db(infos)

    def _save_translation_from_page(self, infos: Entry):
        # summary = "Dikan-teny avy amin'ny pejy avy amin'i %s.wiktionary" % infos.language
        # summary += " (%s)" % get_version()
        # wikipage = self.output.wikipage(infos)
        # target_language_page = pwbot.Page(pwbot.Site(WORKING_WIKI_LANGUAGE, 'wiktionary'), infos.entry)
        # if target_language_page.exists():
        #     page_content = target_language_page.get()
        #     if page_content.find('{{=%s=}}' % infos.language) != -1:
        #         self.output.db(infos)
        #         return
        #     else:
        #         wikipage += page_content
        #         wikipage, edit_summary = Autoformat(wikipage).wikitext()
        #         summary = "+" + summary + ", %s" % edit_summary
        #
        # target_language_page.put_async(wikipage, summary)
        self.output.db(infos)

    def process_entry_in_native_language(
            self,
            content: str,
            title: str,
            language: str,
            unknowns: list):
        """
        Yields each translation found
        :param content:
        :param title:
        :param language:
        :param unknowns:
        :return:
        """
        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(
            language)
        wiktionary_processor = wiktionary_processor_class()
        try:
            wiktionary_processor.set_text(content)
            wiktionary_processor.set_title(title)
            translations = wiktionary_processor.retrieve_translations()
        except Exception as exc:
            log.exception(exc)
            return

        for translation in translations:
            entry = translation.entry
            pos = translation.part_of_speech
            entry_language = translation.language
            if entry_language in self.language_blacklist:  # check in language blacklist
                continue

            try:
                target_language_translations = [
                    t['definition'] for t in
                    self.translate_word(title, language)
                    if t['part_of_speech'] == str(pos)
                ]
            except NoWordException as exc:
                log.debug(
                    'No translation found for %s in %s' %
                    (title, language))
                if title not in unknowns:
                    unknowns.append((title, language))
                break

            infos = Entry(
                entry=entry,
                part_of_speech=str(pos),
                entry_definition=target_language_translations,
                language=entry_language,
                origin_wiktionary_edition=language,
                origin_wiktionary_page_name=title)

            yield infos

    def process_infos(self, infos):
        resp = requests.get(
            URL_HEAD + '/entry/%s/%s' %
            (infos.language, infos.entry))
        if resp.status_code != WordDoesNotExistException.status_code:
            return 1

        self.output.db(infos)
        _generate_redirections(infos)
        self._save_translation_from_bridge_language(infos)
        return 1

    def process_entry_in_foreign_language(
            self,
            entry: Entry,
            title: str,
            language: str,
            unknowns: list):
        if entry.language in self.language_blacklist:
            log.debug(
                "language '%s' is blacklisted, so not translating or processing." %
                language)
            return

        try:
            log.debug(
                "Translating word in foreign language (%s in '%s')" %
                (entry.entry_definition[0], language))
            target_language_translations = []
            for translation in self.translate_word(
                    entry.entry_definition[0], language):
                if translation['part_of_speech'] == entry.part_of_speech:
                    target_language_translations.append(
                        translation['definition'])
            if len(target_language_translations) == 0:
                log.debug("No matching translations found")
                return
        except NoWordException:
            log.debug("No translation found")
            if title not in unknowns:
                unknowns.append((entry.entry_definition[0], language))
            return

        infos = Entry(
            entry=title,
            part_of_speech=str(entry.part_of_speech),
            entry_definition=target_language_translations,
            language=entry.language,
            origin_wiktionary_edition=language,
            origin_wiktionary_page_name=entry.entry_definition[0])

        return infos

    def process_wiktionary_wiki_page(self, wiki_page):
        unknowns = []
        try:
            language = wiki_page.site.language()
        except Exception as exc:
            log.error("Couldn't get language.")
            log.exception(exc)
            return unknowns, 0

        # BEGINNING
        ret = 0
        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(
            language)
        wiktionary_processor = wiktionary_processor_class()

        if wiki_page.title().find(':') != -1:
            return unknowns, ret
        if wiki_page.namespace() != 0:
            return unknowns, ret
        wiktionary_processor.process(wiki_page)

        try:
            entries = wiktionary_processor.getall()
        except Exception as exc:
            log.error("getall() failed.")
            log.exception(exc)
            return unknowns, ret

        for entry in entries:
            if entry.entry is None or entry.entry_definition is None:
                continue

            # Attempt a translation of a possible non-lemma entry.
            # Part of the effort to integrate word_forms.py in the IRC bot.

            if entry.language == language:  # if entry in the content language
                for info in self.process_entry_in_native_language(
                        wiki_page.get(), wiki_page.title(), language, unknowns):
                    ret += self.process_infos(info)
            else:
                info = self.process_entry_in_foreign_language(
                    entry, wiki_page.title(), language, unknowns)
                if info is not None:
                    _generate_redirections(info)
                    self._save_translation_from_bridge_language(info)
                    self._save_translation_from_page(info)
                    ret += 1

        # Malagasy language pages
        # self.update_malagasy_word(translations_in_target_language)

        return unknowns, ret

    @staticmethod
    def translate_word(word: str, language: str):
        url = URL_HEAD + \
            '/translations/%s/%s/%s' % (language, WORKING_WIKI_LANGUAGE, word)
        resp = requests.get(url)
        if resp.status_code == WordDoesNotExistException.status_code:
            raise NoWordException()

        translations_json = resp.json()
        translations = []
        if len(translations_json) < 1:
            raise NoWordException()
        else:
            for t in translations_json:
                q = {
                    'part_of_speech': t['part_of_speech'],
                    'definition': t['definition']
                }
                if q not in translations:
                    translations.append(q)

            log.debug(str(translations))
            return translations

    async def _translate_word(self, word: str, language: str):
        url = URL_HEAD + \
            '/translations/%s/%s/%s' % (language, WORKING_WIKI_LANGUAGE, word)
        async with ClientSession() as client_session:
            async with client_session.get(url) as resp:
                if resp.status == WordDoesNotExistException.status_code:
                    raise NoWordException()

                translations_json = await resp.json()
                translations = []
                if len(translations_json) < 1:
                    raise NoWordException()
                else:
                    for t in translations_json:
                        q = {
                            'part_of_speech': t['part_of_speech'],
                            'definition': t['definition']
                        }
                        if q not in translations:
                            translations.append(q)

                    return translations

    def process_wiktionary_wikitext(
            self,
            title: str,
            language: str,
            content: str):
        """
        Attempt to make a simplified version of all the methods above
        :param title:
        :param language:
        :param content:
        :return:
        """
        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(
            language)
        wiktionary_processor = wiktionary_processor_class()
        wiktionary_processor.set_text(content)
        wiktionary_processor.set_title(title)

        try:
            entries = wiktionary_processor.getall()
        except Exception as exc:
            log.exception(exc)
            return -1

        print(entries)
        for entry in entries:
            if entry.entry is None or entry.entry_definition is None:
                continue

            if entry.language == language:  # if entry in the content language
                pass
                for info in self.process_entry_in_native_language(
                        content, title, language, []):
                    self.process_infos(info)
            else:
                info = self.process_entry_in_foreign_language(
                    entry, title, language, [])
                if info is not None:
                    self.output.db(info)
                    _generate_redirections(info)
                    self._save_translation_from_bridge_language(info)
                    self._save_translation_from_page(info)

        # Malagasy language pages
        # self.update_malagasy_word(translations_in_target_language)


def _generate_redirections(infos):
    redirection_target = infos.entry
    if infos.language in CYRILLIC_ALPHABET_LANGUAGES:
        for char in "́̀":
            if redirection_target.find(char) != -1:
                redirection_target = redirection_target.replace(char, "")
        if redirection_target.find("æ") != -1:
            redirection_target = redirection_target.replace("æ", "ӕ")
        if infos.entry != redirection_target:
            # page = pwbot.Page(pwbot.Site(WORKING_WIKI_LANGUAGE, 'wiktionary'), infos.entry)
            # if not page.exists():
            # page.put_async("#FIHODINANA [[%s]]" % redirection_target,
            # "fihodinana")
            infos.entry = redirection_target


def _get_unaccented_word(word):
    for char in "́̀":
        if word.find(char) != -1:
            word = word.replace(char, "")
    return word
