# -*- coding: utf8 -*-
import time
import re
import sys
import random
import threading
import os
import signal
import traceback

import pywikibot as pwbot

from modules import BJDBmodule, entryprocessor, ircbot, output
import list_wikis

# GLOBAL VARS
global missing_translations
missing_translations = {}
verbose = False
nwikimax = 15
databases = []
data_file = 'conf/dikantenyvaovao/'

def doexit(*args, **kwargs):
    time.sleep(1500000)
    if len(databases)>0:
        for db in databases:
            db.close()
    os.kill(os.getpid(), signal.SIGTERM)


def IRCretrieve(channel=''):
    setThrottle(1)
    x = threading.Thread(target=doexit)
    x.daemon = True
    x.start()

    missing_translations = MissingTranslations()
    if not len(channel):
        channel = 'en'
    bot = IRC_RC_Bot(channel)
    while 1:
        try:
            bot.start()
        except KeyError:
            time.sleep(10)
            continue
        except KeyboardInterrupt:
            missing_translations.update()
            bot.die()
            return


# Throttle Config
def setThrottle(i):
    from pywikibot import throttle
    t = throttle.Throttle(pwbot.Site('mg', 'wiktionary'), mindelay=0, maxdelay=1)
    pwbot.config2.put_throttle = 1
    t.setDelays(i)


def analyse_translations(arg2):
    arg2 = int(arg2)
    missing_tran = MissingTranslations()
    missing_tran.analyse(arg2)


def analyse_edit_hours(arg2):
    tran_per_hour = Translations_per_day_hour()
    tran_per_hour.analyse()
    tran_per_hour.cleanup()


def add_translations(last_x_hours=1):
    """Add translations to the destination language entry
    @last_x_hours all translations added in the last hour
    """
    last_x_hours = int(last_x_hours)
    currt_time = time.time()
    x_hours_ago = time.gmtime(currt_time - last_x_hours * 3600)

    database = BJDBmodule.WordDatabase()
    databases.append(database)
    Ctranslation = Translations_Handler()

    # maka ny dikanteny hita hatry ny ora voalaza
    q = "select * from `%(DB)s`.`%(table)s` where " % database.DB.infos
    q += "`daty` >= '%04d-%02d-%02d %02d:%02d:%02d'" % tuple(x_hours_ago)[:6]

    allwords = database.DB.raw_query(q)
    Mgwords = {}
    count = 0
    for word in allwords:
        count += 1
        if not count % 10000: print count
        for mgtranslation in word[3].split(','):
            mgtranslation = mgtranslation.strip()
            for char in '[]':
                mgtranslation = mgtranslation.replace(char, '')
            try:
                Mgwords[mgtranslation].append((word[5], word[1]))
            except KeyError:
                Mgwords[mgtranslation] = []
                Mgwords[mgtranslation].append((word[5], word[1]))
    print count
    count = 0
    print "lanjan'ny diksionera : ", len(Mgwords)

    for mgword in Mgwords:
        # print Mgwords[mgword]

        mgPage = pwbot.Page(pwbot.Site('mg', "wiktionary"), mgword.decode('latin1'))
        Page_c = u""

        try:
            Page_c = orig = mgPage.get()
            print "original length:", len(Page_c)
        except Exception:
            continue

        ftranslationlist = set(Mgwords[mgword])
        ftranslationlist = list(ftranslationlist)
        Ctranslation.setcontent(Page_c)
        Page_c = Ctranslation.add(ftranslationlist)

        pwbot.output(">>> %s <<<" % mgPage.title())
        print "output length:", len(Page_c)
        Page_c = Page_c.replace("\n]", "")
        pwbot.showDiff(orig, Page_c)
        while 1:
            try:
                # pwbot.output(Page_c)
                mgPage.put_async(Page_c, "+dikanteny")
                break
            except pwbot.exceptions.PageNotSaved:
                print "Tsy nahatahiry ilay pejy... manandrana"
                time.sleep(10)

        count += 1


def process_dump(val):
    import dumpprocessor
    DumpProcessor = dumpprocessor.Translation_finder_in_dump()
    DumpProcessor.run()


class Translations_per_day_hour(object):
    """Edit counter. Sorted by hour of the day. Uses a file."""

    def __init__(self):
        self.translations_per_hour = {}
        self.retrieve()

    def cleanup(self):
        self.retrieve()
        self.update()

    def retrieve(self):
        try:
            translation_needed_file = open(data_file + 'dikantenyvaovao_dikanteny_isakora.txt', 'r')
        except IOError:
            return

        for i in range(24):
            self.translations_per_hour[str(i)] = 0

        for line in translation_needed_file.readlines():
            line = line.strip('\n')
            line = line.split("::")
            if len(line) < 2:
                continue

            self.translations_per_hour[line[0]] += int(line[1].replace(':', ''))

        translation_needed_file.close()

    def add(self, word):
        try:
            self.translations_per_hour[word] += 1
        except KeyError:
            self.translations_per_hour[word] = 1
        return self.translations_per_hour[word]

    def update(self):
        translation_needed_file = open(data_file + 'dikantenyvaovao_dikanteny_isakora.txt', 'w')
        for translation in self.translations_per_hour:
            try:
                filestr = u"%s::%d\n" % (translation, self.translations_per_hour[translation])
                translation_needed_file.write(filestr.encode('utf8'))
            except UnicodeError:
                continue
        translation_needed_file.close()

    def analyse(self):
        if len(self.translations_per_hour) == 0:
            self.retrieve()
        translation_list = []
        for translation in self.translations_per_hour:
            translation_list.append((int(translation), int(self.translations_per_hour[translation])))
        translation_list.sort()
        pwbot.output(" Isa | Ora\n" + 30 * '-')

        for tr in translation_list:
            pwbot.output('%4d | %d' % tr)


class MissingTranslations(object):
    def __init__(self):
        self.retrieve()

    def retrieve(self):
        try:
            translation_needed_file = open(data_file + 'dikantenyvaovao_ilaina.txt', 'r')
        except IOError:
            return

        for line in translation_needed_file.readlines():
            line = line.strip('\n')
            line = line.split("::")
            try:
                missing_translations[line[0]] += int(line[1].replace(':', ''))
            except KeyError:
                missing_translations[line[0]] = 1
        translation_needed_file.close()

    def add(self, word):
        try:
            missing_translations[word] += 1
        except KeyError:
            missing_translations[word] = 1
        return missing_translations[word]

    def update(self):
        translation_needed_file = open(data_file + 'dikantenyvaovao_ilaina.txt', 'w')
        for translation in missing_translations:
            try:
                filestr = u"%s::%d\n" % (translation, missing_translations[translation])
                translation_needed_file.write(filestr.encode('utf8'))
            except UnicodeError:
                continue
        translation_needed_file.close()

    def analyse(self, n_display=10):
        if len(missing_translations) == 0:
            self.retrieve()
        translation_list = []
        for translation in missing_translations:
            translation_list.append((int(missing_translations[translation]), translation))
        translation_list.sort()
        tr_list = translation_list[::-1]
        pwbot.output(" N° Tranga | Teny\n" + 30 * '-')
        tr_list = tr_list[:n_display]

        for tr in tr_list:
            pwbot.output('%10d | %s' % tr)


class IRC_RC_Bot(ircbot.SingleServerIRCBot):
    """IRC client used to track edits on targetted wikis.
    @lang string containing languages of editions to track.
    For example : fr,en,de will track fr.wiktionary, en.wiktionary and de.wiktionary
    @user the username which will be use by the IRC client
    """

    def __init__(self, lang, user="botjagwar-w%x" % random.randint(1, 0xffff)):
        self.username = user
        self.chronometer = 0.0
        self.joined = []
        self.initIRCBot(lang, self.username)

    def initIRCBot(self, lang, user="botjagwar-w%x" % random.randint(1, 0xffff)):
        """Antsoy ity lefa ity raha tia handefa ny rôbô irc an'ity kilasy ity"""
        self.translations = Translation()
        self.iso2languagename = {}
        self.errfile = file(data_file + 'dikantenyvaovao.exceptions', 'a')
        self.stats = {'edits': 0.0, 'newentries': 0.0, 'errors': 0.0}
        self.changelangs(lang)

        self.connect_in_languages(user)
        self.tran_per_hour = Translations_per_day_hour()

    def changelangs(self, langstring):
        self.langs = re.split("\,[ ]?", langstring)

    def connect_in_languages(self, user="botjagwar-w%x" % random.randint(1, 0xffff)):
        """mametaka fitohizana amin'ny tsanely irc an'i Wikimedia"""
        print "\n---------------------\n       PARAMETATRA : "
        lister = list_wikis.Wikilister()
        self.langs = lister.getLangs("wiktionary")
        i = 0
        for language in self.langs:
            if i > nwikimax: break
            i += 1
            if language == 'mg': continue
            language = language.strip()
            self.channel = "#%s.wiktionary" % language
            self.botname = user
            print "kaodim-piteny:", language, ", tsanely:", self.channel, " anarana:", self.botname

            ircbot.SingleServerIRCBot.__init__(self, [("irc.wikimedia.org", 6667)],
                                               self.botname, "Bot-Jagwar [IRCbot v2].")
            self.joined.append(language)
        print "Vita ny fampitohizana"

    def on_welcome(self, serv, ev):
        for language in self.joined:
            # print "Mangataka tonga soa avy amin'i #"+language+".wiktionary"
            serv.join("#" + language + ".wiktionary")

    def on_kick(self, serv, ev):
        for language in self.joined:
            print "Voadaka. Mangataka tonga soa avy amin'i #" + language + ".wiktionary"
            serv.join("#" + language + ".wiktionary")

    def on_pubmsg(self, serv, ev):

        try:
            try:
                message = ev.arguments()[0].decode('utf8')
            except UnicodeDecodeError:
                message = ev.arguments()[0].decode('latin1')
            lang = 'fr'  # fiteny defaulta

            # Fitadiavana ny wiki niavian'ilay hafatra
            try:
                lang = re.search('//([a-z|\-]+).wiktionary', message).groups()[0]
            except AttributeError:
                pwbot.output(message)

            # Fijerena ny teny iditra & fanamboarana ny zavatra mamaritra azy.
            message = message[:message.find('http')]
            item = re.search("\[\[(.*)\]\]", message).groups()[0]
            item = unicode(item[3:-3])
            if len(item) > 70: return
            self.stats['edits'] += 1.
            if item.find(':') != -1:
                return
            Page = pwbot.Page(pwbot.Site(lang, 'wiktionary'), item)

            # teny iditra vokatra
            self.stats['newentries'] += self.translations.process_wiktionary_page(lang,
                                                                                  Page)  # mamerina ny isan'ny pejy voaforona
            self.stats['rend'] = 100. * self.stats['errors'] / self.stats['edits']
            self.stats['rendpejy'] = 100. * float(self.stats['newentries']) / self.stats['edits']

            # interwiki vokatra
            self.translations.process_interwiki(lang, Page)

            # Fanehoana ny statistika
            if not self.stats["edits"] % 5:
                cttime = time.gmtime()
                self.chronometer = time.time() - self.chronometer
                print "%d/%02d/%02d %02d:%02d:%02d > " % cttime[:6], \
                    "Fanovana: %(edits)d; pejy voaforona: %(newentries)d; hadisoana: %(errors)d" % self.stats \
                    + " taha: fanovana %.1f/min" % (
                        60. * (5 / self.chronometer))
                self.chronometer = time.time()

            # fanavaozana ny isan'ny dikanteny
            tran_hour = time.gmtime()[3]
            if self.tran_per_hour.translations_per_hour.has_key(tran_hour):
                self.tran_per_hour.translations_per_hour[tran_hour] += 1
            else:
                self.tran_per_hour.translations_per_hour[tran_hour] = 1
            self.tran_per_hour.update()

        except Exception as e:
            print traceback.format_exc()
            self.stats['errors'] += 1
            errstr = u"\n%s" % (e.message)
            self.errfile.write(errstr.encode('utf8'))


class Translations_Handler(object):
    def __init__(self):
        """Mitantana ny dikantenin'ny teny hafa amin'ny teny malagasy"""
        self.content = u""
        self.loaded_flag = False

    def setcontent(self, content):
        """Tsy maintsy antsoina ity lefa ity alohan'ny miantso ny lefa hafa
           (manipy AssertionError ireo lefa ireo raha tsy manao izany)"""
        self.content = content
        self.loaded_flag = True

    def sort(self):
        """Fampirimana ny dikanteny azo amin'ny alalan'ny REGEX araka ny laharan'ny Abidy"""
        assert self.loaded_flag is True

        if self.content.find('{{}} :') == -1: return self.content
        trads = re.findall("# (.*) : \[\[(.*)\]\]", self.content)
        trads.sort()
        trstr = '{{}} :'
        tran = self.content.replace('{{}} :', '')
        if len(trads) > 200:
            if verbose: print 'hadisoana ?'
            return tran
        for i in trads:
            trstr = trstr.replace("{{}} :", "# %s : [[%s]]\n{{}} :" % i)
            tran = self.content.replace('\n\n', '\n')
        trstr = trstr.strip('\n')
        trstr = re.sub("(\\n)+", "\n", trstr)
        tran = self.content.replace("{{-dika-}}", "{{-dika-}}\n%s" % trstr)

        self.loaded_flag = False
        return self.content.strip('\n')

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
        self.content = re.sub(u"# \{\{[a-z]+\}\} : (.*)[\n]?", "", self.content)

        self.loaded_flag = False
        return self.content  # tuple (entry, lang)

    def get(self):
        """ Maka ny dikanteny rehetran'ny votoatim-pejy."""
        assert self.loaded_flag is True
        translations = re.findall("\{\{dikan\-teny|(.*)|([a-z]+)\}\}", self.content)
        translations.sort()

        self.loaded_flag = False
        return translations

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

        if self.content.find("{{-dika-}}") != -1:
            if self.content.find("{{%s}} :" % (langcode)) != -1:
                if self.content.find(u"{{dikan-teny|%s|%s}}" % (translation, langcode)) != -1:
                    self.content = re.sub("[ ]?\{\{dikan\-teny\|%s\|%s\}\}[\,]?" % (translation, langcode), u"",
                                          self.content)
                    self.content = self.content.replace("# {{%s}} :" % (langcode),
                                                        u"# {{%s}} : {{dikan-teny|%s|%s}}," % (
                                                            langcode, translation, langcode))
                else:
                    self.content = self.content.replace("# {{%s}} :" % (langcode),
                                                        u"# {{%s}} : {{dikan-teny|%s|%s}}," % (
                                                            langcode, translation, langcode))
            else:
                self.content = self.content.replace("{{-dika-}}",
                                                    u"{{-dika-}}\n# {{%s}} : {{dikan-teny|%s|%s}}" % (
                                                        langcode, translation, langcode))

        return self.content


class Translation(Translations_Handler):
    def __init__(self):
        """Mandika teny ary pejy @ teny malagasy"""
        super(self.__class__, self).__init__()
        self.sql_db = BJDBmodule.Database()
        self.word_db = BJDBmodule.WordDatabase()

        databases.append(self.word_db)
        databases.append(self.sql_db)

        self.output = output.Output()
        self.iso2languagename = {}
        self.errlogfile = file(data_file + 'dikantenyvaovao.exceptions', 'a')
        self.langblacklist = ['fr', 'en', 'sh', 'ar', 'de', 'zh']
        self.entryprocessors = {}
        self.translationslist = []

    def _codetoname(self, languageISO):
        if self.iso2languagename == {}:
            # initialise variable
            langfile = open(data_file + "iso2name.txt", 'r')
            for line in langfile.readlines():
                line = line.split(':')
                self.iso2languagename[line[0]] = line[1]
        else:
            return self.iso2languagename

    def process_interwiki(self, lang, Page):
        summary = "Interwiki mivantana [v1]: "
        langlinks = []

        if Page.isRedirectPage():
            return
        if Page.exists():
            langlinks = re.findall("\[\[([a-z]{2,3}):(.*)\]\]", Page.get())
        mgpage = pwbot.Page(pwbot.Site('mg', 'wiktionary'), Page.title())

        if mgpage.exists():
            opage_c = mgpage.get()
            mgpage_c = mgpage.get()
            mgpagelanglinks = re.findall("\[\[([a-z]{2,3}):(.*)\]\]", mgpage_c)
            mgpage_c = re.sub("\n\[\[([a-z]{2,3}):(.*)\]\]", "", mgpage_c)
            mgpage_c = re.sub("\[\[([a-z]{2,3}):(.*)\]\]", "", mgpage_c)
            mgpage_c = re.sub("\n\[\[mg:(.*)\]\]", "", mgpage_c)

            if mgpage_c.find(u"\n[[%s:%s]]" % ((lang, Page.title()))) == -1 and lang != 'mg':
                summary += u"%s, " % lang
                # mgpage_c += u"\n[[%s:%s]]"%((lang, Page.title()))

            if len(langlinks) - 1 < len(mgpagelanglinks):
                return

            langlinks.append((lang, Page.title()))

            langlinks.sort()
            mgpagelanglinks.sort()
            tobeadded = list(mgpagelanglinks)

            for langlink in langlinks:
                if langlink not in mgpagelanglinks:
                    if langlink[0] == 'mg':  # rohy anaty tenin'ny wiki iasana (diso)
                        continue
                    tobeadded.append(langlink)
                    summary += u"%s, " % langlink[0]

            tobeadded.sort()
            for langlink in tobeadded:
                iw = u"\n[[%s:%s]]" % langlink
                mgpage_c = mgpage_c + iw

            summary = summary.strip(u", ")
            if opage_c != mgpage_c:
                pwbot.showDiff(opage_c, mgpage_c)
                mgpage.put_async(mgpage_c, summary)

    def get_allwords(self):
        alldata = self.sql_db.load()
        ret = {}
        for data in alldata:
            if ret.has_key(data[5]):
                ret[data[5]].append(unicode(data[1], 'latin1'))
            else:
                ret[data[5]] = [unicode(data[1], 'latin1')]
        return ret

    def get_alltranslations(self, language='en'):
        alldata = self.sql_db.read({'fiteny': language})
        ret = {}
        for data in alldata:
            if ret.has_key(data[1]):
                ret[data[1]] = unicode(data[3], 'latin1')
            else:
                ret[data[1]] = unicode(data[3], 'latin1')
        return ret

    def translate_word(self, word, language='fr'):
        tr = self.word_db.translate(word, language)
        if not tr:
            raise NoWordException()
        else:
            return tr

    # TODO : refactor
    def process_wiktionary_page(self, language, Page):
        # fanampiana : Page:Page


        def save_translation_from_bridge_language(self, infos):
            summary = "Dikan-teny avy amin'ny dikan-teny avy amin'i %(olang)s.wiktionary" % infos
            wikipage = self.output.wikipage(infos)
            try:
                mg_Page = pwbot.Page(pwbot.Site('mg', 'wiktionary'), infos['entry'])
            except UnicodeDecodeError:
                mg_Page = pwbot.Page(pwbot.Site('mg', 'wiktionary'), infos['entry'].decode('utf8'))

            try:
                if mg_Page.exists():
                    pagecontent = mg_Page.get()
                    if pagecontent.find('{{=%s=}}' % infos['lang']) != -1:
                        if verbose: print "Efa misy ilay teny iditra."
                        self.output.db(infos)
                        return
                    else:
                        wikipage += pagecontent
                        summary = u"+" + summary
            except pwbot.exceptions.IsRedirectPage:
                infos['entry'] = mg_Page.getRedirectTarget().title()
                save_translation_from_bridge_language(self, infos)
                return

            except pwbot.exceptions.InvalidTitle:
                if verbose: print "lohateny tsy mety ho lohatenim-pejy"
                return

            except Exception as e:
                if verbose: print e
                return

            if verbose:
                pwbot.output("\n \03{red}%(entry)s\03{default} : %(lang)s " % infos)
                pwbot.output("\03{white}%s\03{default}" % wikipage)
            mg_Page.put_async(wikipage, summary)
            self.output.db(infos)

        def save_translation_from_page(self, infos):
            summary = "Dikan-teny avy amin'ny pejy avy amin'i %(olang)s.wiktionary" % infos
            wikipage = self.output.wikipage(infos)
            mg_Page = pwbot.Page(pwbot.Site('mg', 'wiktionary'), infos["entry"])
            if mg_Page.exists():
                pagecontent = mg_Page.get()
                if pagecontent.find('{{=%s=}}' % infos['lang']) != -1:
                    if verbose: print "Efa misy ilay teny iditra, fa mbola tsy fantatry ny banky angona izany."
                    self.output.db(infos)
                    return
                else:
                    wikipage += pagecontent
                    summary = u"+" + summary
                    # wikipage = autocleanup.alphasort(wikipage)

            pwbot.output(u"\03{default}>>> \03{lightgreen}%(entry)s\03{default}" % infos
                         + u"<<<\n\03{lightblue}%s\03{default}" % wikipage)
            mg_Page.put_async(wikipage, summary)
            self.output.db(infos)

        def generate_redirections(self, infos):
            redirtarget = infos['entry']
            if infos['lang'] in ['ru', 'uk', 'bg', 'be']:
                for char in u"́̀":
                    if redirtarget.find(char) != -1:
                        redirtarget = redirtarget.replace(char, u"")
                if redirtarget.find(u"æ") != -1:
					redirtarget = redirtarget.replace(u"æ", u"ӕ")
                if infos['entry'] != redirtarget:
                    pwbot.Page(pwbot.Site('mg', 'wiktionary'),
                               infos['entry']).put_async(u"#FIHODINANA [[%s]]" % redirtarget, "fihodinana")
                    infos['entry'] = redirtarget

        def append_in(infos, translations_in_mg):  # TRANSLATION HANDLING SUBFUNCTION
            for mgtranslation in infos['definition'].split(","):
                mgtranslation = mgtranslation.strip()
                if translations_in_mg.has_key(mgtranslation):
                    translations_in_mg[mgtranslation].append((infos["lang"], infos["entry"]))
                else:
                    translations_in_mg[mgtranslation] = []
                    translations_in_mg[mgtranslation].append((infos["lang"], infos["entry"]))

        # BEGINNING
        ret = 0
        processor_class = None
        if verbose: print "Praosesera:", language.upper()
        if language in self.entryprocessors:
            processor_class = self.entryprocessors[language]
        else:
            try:
                self.entryprocessors[language] = entryprocessor.WiktionaryProcessorFactory.new_wiktionary_processor(language)
                processor_class = self.entryprocessors[language]
            except NotImplementedError:
                return 0

        if verbose: pwbot.output("\n >>> \03{lightgreen}%s\03{default} <<< " % Page.title())

        if Page.title().find(':') != -1:
            if verbose: print "Nahitana ':' tao anaty anaram-pejy"
            return ret
        if Page.namespace() != 0:
            if verbose: print "Tsy amin'ny anaran-tsehatra fotony"
            return ret
        processor_class.process(Page)
        entries = []
        try:
            entries = processor_class.getall()
        except Exception:
            return 0
        translations_in_mg = {}  # dictionary {string : list of translation tuple (see below)}
        for entry in entries:
            # entry = (self.title, pos, self.lang2code(l), defin.strip())
            if entry[2] == language:  # if entry in the content language
                # (self.title, pos, self.lang2code(l), defin.strip())
                translations = []
                try:
                    translations = processor_class.retrieve_translations()
                except Exception:
                    continue
                translations_in_mg = {}  # dictionary {string : list of translation tuple (see below)}
                for translation in translations:
                    # translation = tuple(codelangue, entree)
                    if translation[2] in self.langblacklist:  # check in language blacklist
                        if verbose: print "Fiteny voalisi-mainty: ", translation[2]
                        continue
                    try:
                        mg_translation = self.translate_word(Page.title(), language)
                    except NoWordException:
                        Missing_translations.add(Page.title())
                        if verbose: pwbot.output(
                            "Tsy nahitana dikantenin'i '%s' ho an'ny teny '%s' tao amin'ny banky angona" % (
                                Page.title(), language))
                        break
                    infos = {
                        'entry': translation[0],
                        'POS': translation[1],
                        'definition': mg_translation,
                        'lang': translation[2],
                        'olang': language,
                        'origin': Page.title()}

                    if self.word_db.exists(infos['entry'], infos['lang']):
                        # print "Efa fantatra tamin'ny alalan'ny banky angona ny fisian'ilay teny"
                        continue

                    generate_redirections(self, infos)
                    append_in(infos, translations_in_mg)
                    if verbose: print translations_in_mg
                    save_translation_from_bridge_language(self, infos)
                    ret += 1

                    # Malagasy language pages

            else:
                # (self.title, pos, self.lang2code(l), defin.strip())
                if entry[2] in self.langblacklist:
                    if verbose: print "Fiteny voalisi-mainty:", entry[2]
                    continue
                title = Page.title()
                try:
                    mg_translation = self.translate_word(entry[3], language)
                except NoWordException:
                    Missing_translations.add(entry[3])
                    if verbose: pwbot.output(
                        "\03{yellow}Tsy nahitana dikantenin'i '%s' ho an'ny teny '%s' tao amin'ny banky angona\03{default}" % (
                            entry[3], language))
                    continue

                infos = {
                    'entry': title,
                    'POS': entry[1],
                    'definition': mg_translation,
                    'lang': entry[2],
                    'olang': language,
                    'origin': entry[3]}

                if verbose: pwbot.output(
                    "\03{red}%(entry)s\03{default}: dikanteny vaovao amin'ny teny '%(lang)s' " % infos)
                if self.word_db.exists(infos['entry'], infos['lang']):
                    if verbose: print "Efa fantatra tamin'ny alalan'ny banky angona ny fisian'ilay teny"
                    continue

                generate_redirections(self, infos)
                append_in(infos, translations_in_mg)
                if verbose:
                    print translations_in_mg
                save_translation_from_bridge_language(self, infos)
                save_translation_from_page(self, infos)

                ret += 1

        # Malagasy language pages
        # self.update_malagasy_word(translations_in_mg)


        if verbose: print " Vita."
        return ret

    def update_malagasy_word(self, translations_in_mg):
        # Malagasy language pages
        def update_malagasy_word(word, translations):
            mg_entryPage = pwbot.Page(pwbot.Site('mg', 'wiktionary'), word)
            try:
                self.setcontent(mg_entryPage.get())
                content = self.add(translations)
                mg_entryPage.put_async(content, "+dikanteny")
            except pwbot.IsRedirectPage:
                redirtarget = mg_entryPage.getRedirectTarget()
                if verbose:
                    pwbot.output("Pejy fihodinana '%s', manakatra ny tanjony: '%s'" %
                                 (mg_entryPage.title(), redirtarget.title()))
                redirtarget = mg_entryPage.getRedirectTarget()
                update_malagasy_word(redirtarget.title(), translations)

            except pwbot.NoPage:
                if verbose:
                    pwbot.output("Tsy misy ilay pejy '%s'" % mg_entryPage.title())
                return
            except Exception:
                if verbose:
                    pwbot.output("Nisy hadisoana.")
                return

        if verbose: print "Manavao ny pejy malagasy...", "dikanteny %d" % len(translations_in_mg)
        for translation_in_mg in translations_in_mg:
            translation_in_mg = translation_in_mg.strip()
            for char in '[]':
                translation_in_mg = translation_in_mg.replace(char, '')

            translation_in_mg = unicode(translation_in_mg)
            update_malagasy_word(translation_in_mg, translations_in_mg[translation_in_mg])
        if verbose: print "tafapetraka ny dikanteny"

    def exists(self, lang, ent):
        try:
            ent = ent.decode('utf8')
        except UnicodeEncodeError:
            pass

        try:
            lang = unicode(lang, 'latin1')
        except TypeError:
            pass

        if self.translationslist.count((lang, ent)) >= 1:
            return True
        else:
            # pwbot.output(u"mitady an'i teny \"%s\" ao amin'ny banky angona..."%ent)
            if ent == 'en': return self.word_db.exists(ent, lang)
            self.translationslist.append((lang, ent))
            # print type(lang), type(ent)
            return self.word_db.exists(ent, lang)


class NoWordException(Exception):
    def __init__(self):
        pass


def striplinks(link):
    l = link
    for c in ['[', ']']:
        l = l.replace(c, '')
    return l


def testTranslate(val):
    test = Translation()
    verbose = True
    listpagestring = parseErrlog()
    for page in listpagestring:
        page = page.decode('utf8')
        for lang in ['en', 'fr']:
            print lang
            print "------------------"
            Page = pwbot.Page(pwbot.Site(lang, 'wiktionary'), page)
            test.process_wiktionary_page(lang, Page)


def parseErrlog():
    ret = []
    in_file = file(data_file + 'dikantenyvaovao.exceptions', 'r').readlines()
    for item in in_file:
        pwbot.output(item)
        item = item.strip('\n')

        regex = re.search("\[\[(.*)\]\]", item)
        if regex is None:
            continue

        string = regex.groups()[0]
        ret.append(string[3:-3])
    return ret


args = sys.argv

if __name__ == '__main__':
    Missing_translations = MissingTranslations()
    argsdict = {
        'irc': IRCretrieve,
        'debug': testTranslate,
        'analyse': analyse_translations,
        'edittimes': analyse_edit_hours,
        'addtranslations': add_translations,
        'dump': process_dump}
    try:
        # verbose=True
        # print args[1] + " --- " + args[2]
        argsdict[args[1]](args[2])
    finally:
        pwbot.stopme()
