# coding: utf8
import asyncio
import os

import pywikibot as pwbot
from aiohttp import ClientSession

from api import entryprocessor
from api import get_version
from api.autoformatter import Autoformat
from api.exceptions import NoWordException
from api.output import Output
from database.exceptions.http import WordDoesNotExistException
from object_model.word import Entry
from word_forms import create_non_lemma_entry

default_data_file = os.getcwd() + '/conf/entry_translator/'
CYRILLIC_ALPHABET_LANGUAGES = ['ru', 'uk', 'bg', 'be']
LANGUAGE_BLACKLIST = ['fr', 'en', 'sh', 'ar', 'de', 'zh']
URL_HEAD = 'http://localhost:8001'
WORKING_WIKI_LANGUAGE = 'target_language'


class Translation:
    def __init__(self, data_file=False):
        """Mandika teny ary pejy @ teny malagasy"""
        super(self.__class__, self).__init__()
        self.data_file = data_file or default_data_file
        self.output = Output()
        self.language_blacklist = LANGUAGE_BLACKLIST

        self.loop = asyncio.get_event_loop()

    async def _save_translation_from_bridge_language(self, infos):
        summary = "Dikan-teny avy amin'ny dikan-teny avy amin'i %s.wiktionary" % infos.origin_wiktionary_edition
        summary += " (%s)" % get_version()
        wikipage = self.output.wikipage(infos)
        target_language_page = pwbot.Page(pwbot.Site(WORKING_WIKI_LANGUAGE, 'wiktionary'), infos.entry)
        try:
            if target_language_page.exists():
                page_content = target_language_page.get()
                if page_content.find('{{=%s=}}' % infos.language) != -1:
                    await self.output.db(infos)
                    return
                else:
                    wikipage += page_content
                    summary = "+" + summary
        except pwbot.exceptions.IsRedirectPage:
            infos.entry = target_language_page.getRedirectTarget().title()
            await self._save_translation_from_bridge_language(infos)
            return

        except pwbot.exceptions.InvalidTitle:
            return

        except Exception as e:
            return

        target_language_page.put_async(wikipage, summary)
        await self.output.db(infos)

    async def _save_translation_from_page(self, infos):
        summary = "Dikan-teny avy amin'ny pejy avy amin'i %s.wiktionary" % infos.language
        summary += " (%s)" % get_version()
        wikipage = self.output.wikipage(infos)
        target_language_page = pwbot.Page(pwbot.Site(WORKING_WIKI_LANGUAGE, 'wiktionary'), infos.entry)
        if target_language_page.exists():
            page_content = target_language_page.get()
            if page_content.find('{{=%s=}}' % infos.language) != -1:
                await self.output.db(infos)
                return
            else:
                wikipage += page_content
                wikipage, edit_summary = Autoformat(wikipage).wikitext()
                summary = "+" + summary + ", %s" % edit_summary

        target_language_page.put_async(wikipage, summary)
        await self.output.db(infos)

    async def process_entry_in_native_language(self, wiki_page, language, unknowns):

        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(language)
        wiktionary_processor = wiktionary_processor_class()
        ret = 0
        try:
            translations = wiktionary_processor.retrieve_translations()
        except Exception as e:
            return ret
        for translation in translations:
            entry = translation.entry
            pos = translation.part_of_speech
            entry_language = translation.language
            if entry_language in self.language_blacklist:  # check in language blacklist
                continue

            title = wiki_page.title()
            try:
                target_language_translations = await self.translate_word(title, language)
            except NoWordException:
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
            async with ClientSession() as client_session:
                async with client_session.get(URL_HEAD + '/word/%s/%s' % (infos.language, infos.entry)) as resp:
                    if resp.status != WordDoesNotExistException.status_code:
                        continue

            _generate_redirections(infos)
            await self._save_translation_from_bridge_language(infos)
            ret += 1

        return ret

    async def process_entry_in_foreign_language(self, entry: Entry, wiki_page, language, unknowns):
        if entry.language in self.language_blacklist:
            return 0

        async with ClientSession() as client_session:
            async with client_session.get(URL_HEAD + '/word/%s/%s' % (language, entry.entry)) as resp:
                if resp.status != WordDoesNotExistException.status_code:
                    return 0

        title = wiki_page.title()
        try:
            target_language_translations = await self.translate_word(entry.entry_definition[0], language)
        except NoWordException:
            if title not in unknowns:
                unknowns.append((entry.entry_definition[0], language))
            return 0

        infos = Entry(
            entry=title,
            part_of_speech=str(entry.part_of_speech),
            entry_definition=target_language_translations,
            language=entry.language,
            origin_wiktionary_edition=language,
            origin_wiktionary_page_name=entry.entry_definition[0])

        _generate_redirections(infos)
        await self._save_translation_from_bridge_language(infos)
        await self._save_translation_from_page(infos)

        return 1

    async def process_wiktionary_wiki_page(self, wiki_page):
        unknowns = []
        try:
            language = wiki_page.site.language()
        except Exception:
            return unknowns, 0

        # BEGINNING
        ret = 0
        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(language)
        wiktionary_processor = wiktionary_processor_class()

        if wiki_page.title().find(':') != -1:
            return unknowns, ret
        if wiki_page.namespace() != 0:
            return unknowns, ret
        wiktionary_processor.process(wiki_page)

        try:
            entries = wiktionary_processor.getall()
        except Exception as e:
            return unknowns, ret

        for entry in entries:
            if entry.entry is None or entry.entry_definition is None:
                continue

            # Attempt a translation of a possible non-lemma entry.
            # Part of the effort to integrate word_forms.py in the IRC bot.
            ret += create_non_lemma_entry(entry)

            if entry.language == language:  # if entry in the content language
                ret += await self.process_entry_in_native_language(
                        wiki_page, language, unknowns)
            else:
                ret += await self.process_entry_in_foreign_language(
                        entry, wiki_page, language, unknowns)

        # Malagasy language pages
        # self.update_malagasy_word(translations_in_target_language)

        return unknowns, ret

    async def translate_word(self, word: str, language: str):
        url = URL_HEAD + '/translations/%s/%s/%s' % (language, WORKING_WIKI_LANGUAGE, word)
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
                if t['definition'] not in translations:
                    translations.append(t['definition'])

            return translations


def _generate_redirections(infos):
    redirection_target = infos.entry
    if infos.language in CYRILLIC_ALPHABET_LANGUAGES:
        for char in "́̀":
            if redirection_target.find(char) != -1:
                redirection_target = redirection_target.replace(char, "")
        if redirection_target.find("æ") != -1:
            redirection_target = redirection_target.replace("æ", "ӕ")
        if infos.entry != redirection_target:
            page = pwbot.Page(pwbot.Site(WORKING_WIKI_LANGUAGE, 'wiktionary'), infos.entry)
            if not page.exists():
                page.put_async("#FIHODINANA [[%s]]" % redirection_target, "fihodinana")
            infos.entry = redirection_target
