# coding: utf8
import re
import os
import pywikibot as pwbot
from modules import entryprocessor
from modules.database import Database
from modules.database.word import WordDatabase
from modules.exceptions import NoWordException
from modules.output import Output
from modules.autoformatter import Autoformat
from models.word import Entry

default_data_file = os.getcwd() + '/conf/dikantenyvaovao/'


class TranslationsHandler(object):
    def __init__(self):
        """Mitantana ny dikantenin'ny teny hafa amin'ny teny malagasy"""
        self.content = u""
        self.loaded_flag = False
        self.databases = []

    def _add(self, langcode, translation):
        """ Tao fanampiana dikanteny. Mamerina ny votoatim-pejy misy ny dikanteny."""
        try:
            langcode = unicode(langcode)
        except UnicodeError:
            return self.content

        try:
            translation = unicode(translation, 'utf8')
        except UnicodeDecodeError:
            translation = unicode(translation, 'latin1')
        except TypeError:
            pass

        if self.content.find(u"{{-dika-}}") != -1:
            if self.content.find(u"{{%s}} :" % (langcode)) != -1:
                if self.content.find(u"{{dikan-teny|%s|%s}}" % (translation, langcode)) != -1:
                    self.content = re.sub(r"[ ]?\{\{dikan\-teny\|%s\|%s\}\}[\,]?" % (translation, langcode), u"",
                                          self.content)
                    self.content = self.content.replace(u"# {{%s}} :" % (langcode),
                                                        u"# {{%s}} : {{dikan-teny|%s|%s}}," % (
                                                            langcode, translation, langcode))
                else:
                    self.content = self.content.replace(u"# {{%s}} :" % (langcode),
                                                        u"# {{%s}} : {{dikan-teny|%s|%s}}," % (
                                                            langcode, translation, langcode))
            else:
                self.content = self.content.replace(u"{{-dika-}}",
                                                    u"{{-dika-}}\n# {{%s}} : {{dikan-teny|%s|%s}}" % (
                                                        langcode, translation, langcode))
        return self.content

    def add(self, translations, sort=True):
        """ Afaka mampiditra ny dikanteny eo ambany"""
        assert self.loaded_flag is True

        translations = list(set(translations))
        if sort:
            translations.sort()
        for foreign_translations_tuple in translations[::-1]:
            self.content = self._add(foreign_translations_tuple[0], foreign_translations_tuple[1])

        self.loaded_flag = False
        return self.content

    def delete(self):
        """ Mamerina ny votoatim-pejy tsy misy ny dikanteny."""
        # c1 = self.content.find("{{-dika-}}")
        assert self.loaded_flag is True
        self.content = re.sub(r"# \{\{[a-z]+\}\} : (.*)[\n]?", "", self.content)

        self.loaded_flag = False
        return self.content  # tuple (entry, lang)

    def get(self):
        """ Maka ny dikanteny rehetran'ny votoatim-pejy."""
        assert self.loaded_flag is True
        translations = re.findall(r"\{\{dikan\-teny|(.*)|([a-z]+)\}\}", self.content)
        translations.sort()

        self.loaded_flag = False
        return translations

    def setcontent(self, content):
        """Tsy maintsy antsoina ity lefa ity alohan'ny miantso ny lefa hafa
           (manipy AssertionError ireo lefa ireo raha tsy manao izany)"""
        self.content = content
        self.loaded_flag = True

    def sort(self):
        """Fampirimana ny dikanteny azo amin'ny alalan'ny REGEX araka ny laharan'ny Abidy"""
        assert self.loaded_flag is True

        if self.content.find(u'{{}} :') == -1: return self.content
        trads = re.findall("# (.*) : \[\[(.*)\]\]", self.content)
        trads.sort()
        trstr = u'{{}} :'
        tran = self.content.replace('{{}} :', '')
        if len(trads) > 200:
            return tran
        for i in trads:
            trstr = trstr.replace(u"{{}} :", u"# %s : [[%s]]\n{{}} :" % i)
            tran = self.content.replace('\n\n', '\n')
        trstr = trstr.strip('\n')
        trstr = re.sub("(\\n)+", "\n", trstr)
        tran = self.content.replace(u"{{-dika-}}", u"{{-dika-}}\n%s" % trstr)

        self.loaded_flag = False
        return self.content.strip('\n')


class Translation(TranslationsHandler):
    def __init__(self, data_file=False):
        """Mandika teny ary pejy @ teny malagasy"""
        super(self.__class__, self).__init__()
        self.data_file = data_file or default_data_file
        self.sql_db = Database()
        self.word_db = WordDatabase()
        self.databases.append(self.word_db)
        self.databases.append(self.sql_db)
        self.output = Output()
        self.iso2languagename = {}
        self.errlogfile = file(self.data_file + 'dikantenyvaovao.exceptions', 'a')
        self.langblacklist = ['fr', 'en', 'sh', 'ar', 'de', 'zh']
        self.translationslist = []

    def _save_translation_from_bridge_language(self, infos):
        summary = u"Dikan-teny avy amin'ny dikan-teny avy amin'i %s.wiktionary" % infos.origin_wiktionary_edition
        wikipage = self.output.wikipage(infos)
        try:
            mg_page = pwbot.Page(pwbot.Site('mg', 'wiktionary'), infos.entry)
        except UnicodeDecodeError:
            mg_page = pwbot.Page(pwbot.Site('mg', 'wiktionary'), infos.entry.decode('utf8'))

        try:
            if mg_page.exists():
                pagecontent = mg_page.get()
                if pagecontent.find(u'{{=%s=}}' % infos.language) != -1:
                    self.output.db(infos)
                    return
                else:
                    wikipage += pagecontent
                    summary = u"+" + summary
        except pwbot.exceptions.IsRedirectPage:
            infos.entry = mg_page.getRedirectTarget().title()
            self._save_translation_from_bridge_language(infos)
            return

        except pwbot.exceptions.InvalidTitle:
            return

        except Exception as e:
            return

        pwbot.output(u"\n \03{red}%(entry)s\03{default} : %(language)s " % infos.properties)
        pwbot.output(u"\03{white}%s\03{default}" % wikipage)
        mg_page.put_async(wikipage, summary)
        self.output.db(infos)

    def _save_translation_from_page(self, infos):
        summary = u"Dikan-teny avy amin'ny pejy avy amin'i %s.wiktionary" % infos.language
        wikipage = self.output.wikipage(infos)
        mg_page = pwbot.Page(pwbot.Site('mg', 'wiktionary'), infos.entry)
        if mg_page.exists():
            pagecontent = mg_page.get()
            if pagecontent.find(u'{{=%s=}}' % infos.language) != -1:
                self.output.db(infos)
                return
            else:
                wikipage += pagecontent
                wikipage, edit_summary = Autoformat(wikipage).wikitext()
                summary = u"+" + summary + u", %s" % edit_summary

        pwbot.output(u"\03{default}>>> \03{lightgreen}%(entry)s\03{default}" % infos.properties
                     + u"<<<\n\03{lightblue}%s\03{default}" % wikipage)
        mg_page.put_async(wikipage, summary)
        self.output.db(infos)

    def exists(self, lang, ent):
        ent = ent.decode('utf8')
        lang = lang.decode('latin1')

        if self.translationslist.count((lang, ent)) >= 1:
            return True
        else:
            # pwbot.output(u"mitady an'i teny \"%s\" ao amin'ny banky angona..."%ent)
            return self.word_db.exists(ent, lang)

    def get_allwords(self):
        alldata = self.sql_db.load()
        ret = {}
        for data in alldata:
            if data[5] in ret:
                ret[data[5]].append(unicode(data[1], 'latin1'))
            else:
                ret[data[5]] = [unicode(data[1], 'latin1')]
        return ret

    def get_alltranslations(self, language=u'en'):
        alldata = self.sql_db.read({u'fiteny': language})
        ret = {}
        for data in alldata:
            if ret.has_key(data[1]):
                ret[data[1]] = unicode(data[3], 'latin1')
            else:
                ret[data[1]] = unicode(data[3], 'latin1')
        return ret

    def process_entry_in_native_language(self, wiki_page, language, unknowns):
        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(language)
        wiktionary_processor = wiktionary_processor_class()
        ret = 0
        try:
            translations = wiktionary_processor.retrieve_translations()
        except Exception as e:
            return ret
        translations_in_mg = {}  # dictionary {string : list of translation tuple (see below)}
        for entry, pos, entry_language in translations:
            # translation = tuple(codelangue, entree)
            if entry_language in self.langblacklist:  # check in language blacklist
                continue
            title = wiki_page.title()
            try:
                mg_translation = self.translate_word(title, language)
            except NoWordException:
                if title not in unknowns:
                    unknowns.append((title, language))
                break

            infos = Entry(
                entry=entry,
                part_of_speech=pos,
                entry_definition=mg_translation,
                language=entry_language,
                origin_wiktionary_edition=language,
                origin_wiktionary_page_name=title)
            if self.word_db.exists(infos.entry, infos.language):
                continue

            _generate_redirections(infos)
            _append_in(infos, translations_in_mg)
            self._save_translation_from_bridge_language(infos)
            ret += 1

        return ret

    def process_entry_in_foreign_language(
            self, wiki_page, word, language_code, language, pos, definition, translations_in_mg, unknowns):
        if language_code in self.langblacklist:
            return 0

        if self.word_db.exists(word, language_code):
            return 0

        title = wiki_page.title()
        try:
            mg_translation = self.translate_word(definition, language)
        except NoWordException:
            if title not in unknowns:
                unknowns.append((definition, language))
            return 0

        infos = Entry(
            entry=title,
            part_of_speech=pos,
            entry_definition=mg_translation,
            language=language_code,
            origin_wiktionary_edition=language,
            origin_wiktionary_page_name=definition)

        _generate_redirections(infos)
        _append_in(infos, translations_in_mg)
        self._save_translation_from_bridge_language(infos)
        self._save_translation_from_page(infos)

        return 1

    def process_wiktionary_wiki_page(self, language, Page):
        assert type(language) is unicode
        unknowns = []
        # fanampiana : Page:Page

        # BEGINNING
        ret = 0
        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(language)
        wiktionary_processor = wiktionary_processor_class()

        if Page.title().find(u':') != -1:
            return unknowns, ret
        if Page.namespace() != 0:
            return unknowns, ret
        wiktionary_processor.process(Page)

        try:
            entries = wiktionary_processor.getall()
        except Exception as e:
            return unknowns, ret

        translations_in_mg = {}  # dictionary {string : list of translation tuple (see below)}
        for word, pos, language_code, definition in entries:
            if word is None or definition is None:
                continue

            if language_code == language:  # if entry in the content language
                ret += self.process_entry_in_native_language(Page, language, unknowns)
            else:
                ret += self.process_entry_in_foreign_language(
                    Page, word, language_code, language, pos, definition, translations_in_mg, unknowns)

        # Malagasy language pages
        # self.update_malagasy_word(translations_in_mg)
        return unknowns, ret

    def translate_word(self, word, language='fr'):
        tr = self.word_db.translate(word, language)
        if not tr:
            raise NoWordException()
        else:
            return tr

    def update_malagasy_word(self, translations_in_mg):
        # Malagasy language pages
        def update_malagasy_word(word, translations):
            mg_entry_page = pwbot.Page(pwbot.Site('mg', 'wiktionary'), word)
            try:
                self.setcontent(mg_entry_page.get())
                content = self.add(translations)
                mg_entry_page.put_async(content, u"+dikanteny")
            except pwbot.IsRedirectPage:
                redirtarget = mg_entry_page.getRedirectTarget()
                update_malagasy_word(redirtarget.title(), translations)

            except pwbot.NoPage:
                return
            except Exception as e:
                return

        for translation_in_mg in translations_in_mg:
            translation_in_mg = translation_in_mg.strip()
            for char in '[]':
                translation_in_mg = translation_in_mg.replace(char, '')

            translation_in_mg = unicode(translation_in_mg)
            update_malagasy_word(translation_in_mg, translations_in_mg[translation_in_mg])


def _append_in(infos, translations_in_mg):  # TRANSLATION HANDLING SUBFUNCTION
    for malagasy_translation in infos.entry_definition.split(","):
        malagasy_translation = malagasy_translation.strip()
        if translations_in_mg.has_key(malagasy_translation):
            translations_in_mg[malagasy_translation].append((infos.language, infos.entry))
        else:
            translations_in_mg[malagasy_translation] = []
            translations_in_mg[malagasy_translation].append((infos.language, infos.entry))


def _generate_redirections(infos):
    redirection_target = infos.entry
    if infos.language in ['ru', 'uk', 'bg', 'be']:
        for char in u"́̀":
            if redirection_target.find(char) != -1:
                redirection_target = redirection_target.replace(char, u"")
        if redirection_target.find(u"æ") != -1:
            redirection_target = redirection_target.replace(u"æ", u"ӕ")
        if infos.entry != redirection_target:
            page = pwbot.Page(pwbot.Site('mg', 'wiktionary'), infos.entry)
            if not page.exists():
                page.put_async(u"#FIHODINANA [[%s]]" % redirection_target, u"fihodinana")
            infos.entry = redirection_target