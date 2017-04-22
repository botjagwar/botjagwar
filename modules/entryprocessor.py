import re, time
import pywikibot as wikipedia

data_file = 'conf/entryprocessor/'


def ProcessWikt(language):
    return eval("process_%swikt()" % language)


class WiktionaryProcessorFactory:
    @staticmethod
    def new_wiktionary_processor(language):
        processors = {
            'en': process_enwikt,
            'fr': process_frwikt,
            'vo': process_vowikt,
            'zh': process_zhwikt,
            'de': process_dewikt,
            'pl': process_plwikt}
        if language in processors:
            return processors[language]()
        else:
            raise NotImplementedError("Tsy nahitana praosesera")


class Dump_pagegenerator():
    def __init__(self, dumpfile, language):
        self.dumpfile = None
        self.list_translations = []
        self.newentries = []
        self.language = language
        self.alltranslations = {}
        self.file = wikipedia.xmlreader.XmlDump(dumpfile)
        self.langblacklist = ['fr', 'en', 'sh', 'de', 'zh']

    def load(self, dumptype, filename, language):
        if dumptype == 'dump':
            self.load_dump(data_file + filename, language)
        elif dumptype == 'titles':
            self.load_titlefile(data_file + filename, language)
            self.process = self.process_titlelist

    def load_dump(self, filename, language='en'):
        self.language = language
        self.file = wikipedia.xmlreader.XmlDump(filename)

    def load_titlefile(self, filename, language='en'):
        self.language = language
        self.file = file(filename, 'r').readlines()

    def get_processed_pages(self):
        if self.language == 'en':
            wiktprocessor = process_enwikt()
        elif self.language == 'fr':
            wiktprocessor = process_frwikt()

        print "getting entry translation"
        for fileentry in self.file.parse():
            wiktprocessor.process(fileentry.text, fileentry.title)
            yield wiktprocessor.retrieve_translations()

        print "getting entry page"
        for fileentry in self.file.parse():
            wiktprocessor.process(fileentry.text, fileentry.title)
            yield wiktprocessor.getall()


class wiktprocessor(object):
    """Mother class of all Wiktionary page processors"""

    def __init__(self, test=False, verbose=False):
        self.content = None
        self.Page = None
        self.verbose = verbose
        self.text_set = False

    def process(self, page):
        self.Page = page
        if not self.text_set:
            try:
                self.content = page.get()
            except Exception:
                self.content = u""

    def set_text(self, text):
        self.content = text
        self.text_set = True

    def retrieve_translations(self, page_c):
        print "Not implemented"
        raise NotImplementedError

    def getall(self, keepNativeEntries=False):
        print  "Not implemented"
        raise NotImplementedError


class process_vowikt(wiktprocessor):
    def get_WW_definition(self):
        return self._get_param_in_temp(u"Samafomot:VpVöd", 'WW')

    def _get_param_in_temp(self, templatestr, parameterstr):
        # print templatestr, parameterstr
        RET_text = u""
        templates_withparams = self.Page.templatesWithParams()
        for template in templates_withparams:
            if template[0].title() == templatestr:
                for params in template[1]:
                    if params.startswith(parameterstr + u'='):
                        RET_text = params[len(parameterstr) + 1:]
        return RET_text

    def getall(self, keepNativeEntries=False):
        POStran = {u"värb": 'mat',
                   u'subsat': 'ana',
                   u'ladyek': 'mpam-ana'}

        POS = self._get_param_in_temp(u'Samafomot:VpVöd', u'klad')
        definition = self.get_WW_definition()
        if POStran.has_key(POS):
            postran = POStran[POS]
        else:
            postran = POS

        return (postran, 'vo', definition)

    def retrieve_translations(self, page_c):
        pass


class process_ruwikt(wiktprocessor):
    pass


class process_zhwikt(wiktprocessor):
    pass


class process_dewikt(wiktprocessor):
    pass


class process_plwikt(wiktprocessor):
    def __init__(self, test=False, verbose=False):
        super(process_plwikt, self).__init__(test=False, verbose=False)
        try:
            f = file(data_file + 'plwikt_langdata.dct', 'r').read()
            self.langdata = eval(f)
        except IOError:
            self.langdata = {}

    def retrieve_translations(self, page_c):
        ret = []
        tr_lines = self._get_translation_lines(page_c)
        for line in tr_lines:
            line = line.split(':')
            language = self.langname2languagecode(line[0].strip())
            translations = line[1].strip()
            for translation in translations.split(';'):
                ret.append((language, translation))
        return ret

    def _get_translation_lines(self, page_c):
        ret = []
        # getting borders of translation section
        tr_start = page_c.find(u"== polski ({{język polski}}) ==") + len(u"== polski ({{język polski}}) ==")
        if page_c.find(u"{{tłumaczenia}}", tr_start) != -1:
            tr_start = page_c.find(u"{{tłumaczenia}}", tr_start)
        else:
            return ret
        if page_c.find(u"{{źródła}}", tr_start) != -1:
            tr_end = page_c.find(u"{{źródła}}", tr_start)
        tr_section = page_c[tr_start:tr_end]
        # retrieving translations using regexes
        regex = re.compile('\*(.*)')
        for translation in re.findall(regex, tr_section):
            ret.append(translation)
        return ret

    def _langname2langcode(self, langname):
        langname = langname.strip()
        return self.langdata[langname]


class process_mgwikt(wiktprocessor):
    def __init__(self, test=False, verbose=False):
        self.content = None

    def retrieve_translations(self, page_c):  # Needs updating
        """Fampirimana ny dikanteny azo amin'ny alalan'ny REGEX araka ny laharan'ny Abidy"""
        ret = []
        if page_c.find('{{}} :') == -1: return ret
        trads = re.findall("# (.*) : \[\[(.*)\]\]", page_c)
        trads.sort()
        tran = re.sub("# (.*) : \[\[(.*)\]\]", '', page_c)
        tran = tran.strip('\n')
        trstr = '{{}} :'
        tran = tran.replace('{{}} :', '')
        if len(trads) > 200:
            if self.verbose: print 'hadisoana ?'
            return tran
        for i in trads:
            trstr = trstr.replace("{{}} :", "# %s : [[%s]]\n{{}} :" % i)
            ret.append(i)

        return ret

    def getall(self, keepNativeEntries=False):
        items = []
        for lang in re.findall('\{\{\-([a-z]{3,7})\-\|([a-z]{2,3})\}\}', self.content):
            # word DEFINITION Retrieving
            d1 = self.content.find("{{-%s-|%s}}" % lang) + len("{{-%s-|%s}}" % lang)
            d2 = self.content.find("=={{=", d1) + 1 or self.content.find("== {{=", d1) + 1
            if d2:
                definition = self.content[d1:d2]
            else:
                definition = self.content[d1:]
            try:
                definition = definition.split('\n# ')[1]
            except IndexError:
                # print " Hadisoana : Tsy nahitana famaritana"
                continue
            if (definition.find('\n') + 1):
                definition = definition[:definition.find('\n')]
                definition = re.sub("\[\[(.*)#(.*)\|?\]?\]?", "\\1", definition)
            definition = stripwikitext(definition)
            if not definition:
                continue

            else:
                i = (lang[0].strip(),  # POS
                     lang[1].strip(),  # lang
                     definition)
                items.append(i)
                # wikipedia.output(u" %s --> %s : %s"%i)
        # print "Nahitana dikanteny ", len(items) ", len(items)
        return items


class process_frwikt(wiktprocessor):
    def __init__(self, test=False, verbose=False):
        self.verbose = verbose
        self.text_set = False
        self.content = None
        self.postran = {
            u'verbe': 'mat',
            u'adjectif': 'mpam',
            u'nom': 'ana',
            u'adverbe': 'tamb',
            u'pronom': 'solo-ana',
            u'préfixe': 'tovona',
            u'suffixe': 'tovana'
        }

    def retrieve_translations(self):
        retcontent = []
        regex = '\{\{trad[\+\-]+?\|([A-Za-z]{2,3})\|(.*?)\}\}'
        pos = 'ana'
        defin = u""
        for allentrys in self.getall():  # (self.title, pos, self.lang2code(l), defin.strip())
            if allentrys[2] == 'fr':
                pos = allentrys[1]
                if self.postran.has_key(pos):
                    pos = self.postran[pos]
                defin = allentrys[3]
                break

        for entry in re.findall(regex, self.content):
            langcode = entry[0]
            entree = entry[1]
            try:
                entree = unicode(entry[1])
            except UnicodeDecodeError:
                entree = unicode(entry[1], 'latin1')

            for x in "();:.,":
                if entry[1].find(x) != -1:
                    continue
            if entry[1].find('|') != -1:
                entree = entree.split("|")[0]

            if self.postran.has_key(pos):
                pos = self.postran[allentrys[1]]
            e = (entree, pos, langcode, defin.strip())  # (
            retcontent.append(e)
        try:
            retcontent.sort()
        except UnicodeError:
            pass

        return retcontent

    def getall(self, keepNativeEntries=False):
        """languges sections in a given page formatting: [(POS, lang, definition), ...]"""
        assert type(self.Page) is wikipedia.Page
        items = []

        if self.content is None:
            raise Exception("self.page tsy voafaritra. self.process() tsy mbola nantsoina")

        ct_content = self.content
        for lang in re.findall(
                '\{\{S\|([a-z]+)\|([a-z]{2,3})',
                self.content):
            # print ct_content
            # word DEFINITION Retrieving
            d1 = ct_content.find("{{S|%s|%s" % lang)
            d2 = ct_content.find("=={{langue|", d1) + 1
            if not d2:
                d2 = ct_content.find("== {{langue|", d1 + 50) + 1
            d_ptr = ct_content.find("=={{langue|%s" % lang[1], d1) + 1
            if not d_ptr:
                d_ptr = ct_content.find("== {{langue|%s" % lang[1], d1) + 1

            if d2 > d1:
                definition = ct_content[d1:d2]
            else:
                definition = ct_content[d1:]
            try:
                definition = definition.split('\n# ')[1]
                definition = re.sub("\[\[(.*)#(.*)\|?[.*]?\]?\]?", "\\1", definition)
            except IndexError:
                print " Hadisoana : Tsy nahitana famaritana"
                ct_content = ct_content[d_ptr:]
                continue

            ct_content = ct_content[d_ptr:]
            if definition.find('\n') + 1:
                definition = definition[:definition.find('\n')]

            definition = stripwikitext(definition)
            if not definition:
                ct_content = ct_content[d_ptr:]
                continue

            if lang[1].strip() == 'fr':
                pass
            else:
                pos = frpos = lang[0].strip()  # POS
                if self.postran.has_key(frpos):
                    pos = self.postran[frpos]

                i = (self.Page.title(),
                     pos,  # POS
                     lang[1].strip(),  # lang
                     definition)
                items.append(i)
                # wikipedia.output(u" %s --> %s : %s"%i)
        # print "Nahitana dikanteny ", len(items)
        return items


class process_enwikt(wiktprocessor):
    def __init__(self, test=False, verbose=False):
        self.verbose = verbose
        self.text_set = False
        self.test = test
        self.postran = {
            'Verb': 'mat',
            'Adjective': 'mpam',
            'Noun': 'ana',
            'Adverb': 'tamb',
            'Pronoun': 'solo-ana',
            'Prefix': 'tovona',
            'Suffix': 'tovana'
        }
        self.regexesrep = {
            r"\[\[(.*)#(.*)\|?[.*]?\]?\]?": "\\1",
            r"\{\{(.*)\}\}": "",
            r"\{\{l\|en\|([a-z]+)\}\}": "\\1",
            r"\((.*)\)": ""}
        self.verbose = verbose

        self.code = {}
        dictfile = file(data_file + 'languagecodes.dct', 'r')
        f = dictfile.read()
        try:
            self.code = eval(f)
        except SyntaxError:
            pass
        finally:
            dictfile.close()

    def lang2code(self, l):
        return self.code[l]

    def retrieve_translations(self):
        """Maka ny dikanteny ao amin'ny pejy iray"""
        retcontent = []
        regex = '\{\{t[\+\-]+?\|([A-Za-z]{2,3})\|(.*?)\}\}'
        pos = 'ana'
        defin = u""
        for allentrys in self.getall():  # (self.title, pos, self.lang2code(l), defin.strip())
            if allentrys[2] == 'en':
                pos = allentrys[1]
                defin = allentrys[3]
                break

        for entry in re.findall(regex, self.content):
            langcode = entry[0]
            entree = entry[1]
            try:
                entree = unicode(entry[1])
            except UnicodeDecodeError:
                entree = unicode(entry[1], 'latin1')

            for x in "();:.,":
                if entry[1].find(x) != -1:
                    continue
            if entry[1].find('|') != -1:
                entree = entree.split("|")[0]

            e = (entree, pos, langcode, defin.strip())  # (
            retcontent.append(e)
        try:
            retcontent.sort()
        except UnicodeError:
            pass
        # print "Nahitana dikanteny ", len(retcontent)
        return retcontent  # liste( (codelangue, entrée)... )

    def retrieve_etymologies(self):
        """Maka ny etimolojia rehetra amin'ny teny iray"""

        # Etimolojia manta avy amin'ny fizarana rehetra
        etim = re.findall("===[ ]?Etymology[ ]?[1-9]?===[\n](.*)[\n]+[=]+", self.content)
        print etim
        return etim

    def getall(self):
        items = []
        c = self.content
        c = re.sub('Etymology', '', c)  # famafana ny etimilojia
        c = re.sub("\{\{l\/en\|(.*)\}\}", "\\1 ", c)  # fanovana ny endrika {{l/en}}

        for l in re.findall("[\n]?==[ ]?([A-Za-z]+)[ ]?==\n", c):
            c = c[c.find('==%s==' % l):]

            # pos
            pos = ''
            ptext = regex_ptext = ''
            for p in self.postran:
                regex_ptext += '%s|' % p
            regex_ptext = regex_ptext.strip('|')

            ptext = '\n={4}[ ]?(%s)[ ]?={4}\n' % regex_ptext
            if re.search(ptext, c) is None:
                ptext = '\n={3}[ ]?(%s)[ ]?={3}\n' % regex_ptext
            posregex = re.findall(ptext, c)

            c = re.sub('\[\[(.*)#English\|(.*)\]\]', '\\1', c)
            c = re.sub('\[\[(.*)\|(.*)\]\]', '\\1', c)

            # definition
            try:
                defin = c.split('\n#')[1]
                if defin.find('\n') != -1:
                    defin = defin[:defin.find('\n')]
            except IndexError:
                if self.verbose: print "Hadisoana indexerror."
                continue

            for regex in self.regexesrep:
                defin = re.sub(regex, self.regexesrep[regex], defin).strip()

            for char in '[]':
                defin = defin.replace(char, '')

            defins = defin.split(',')
            if len(defins) > 1:
                defin = defins[0]

            # print ptext
            for p in posregex:
                if p not in self.postran:
                    if self.verbose: print "Tsy ao amin'ny lisitry ny karazanteny fantatra ilay teny"
                    continue
                else:
                    pos = p
                    break
            try:
                pos = self.postran[pos]
            except KeyError:
                if self.verbose: print "Tsy nahitana dikan'ny karazan-teny %s" % pos
                continue
            if defin.startswith('to ') or defin.startswith('To '):
                pos = 'mat'
                defin = defin[2:]
            elif defin.startswith('a ') or defin.startswith('A '):
                pos = 'ana'
                defin = defin[1:]
            if len(defin.strip()) < 1: continue
            try:
                i = (self.Page.title(),
                     pos,
                     self.lang2code(l),
                     defin.strip())  # (
                if self.verbose: wikipedia.output('%s --> teny  "%s" ; famaritana: %s' % i)
                items.append(i)
            except KeyError:
                continue

        # print "Nahitana dikanteny ", len(items)
        return items


def lang2code(l):
    dictfile = file(data_file + 'languagecodes.dct', 'r')
    f = dictfile.read()
    d = eval(f)
    dictfile.close()

    return d[l]


def test(imput=False):
    f = process_frwikt()
    p = wikipedia.Page(wikipedia.Site('fr', 'wiktionary'), imput)
    f.process(p)
    print f.getall()


def stripwikitext(w):
    w = re.sub('[ ]?\[\[(.*)\|(.*)\]\][ ]?', '\\1', w)
    w = w.replace('.', '')
    w = re.sub('[ ]?\{\{(.*)\}\}[ ]?', '', w)
    for c in '[]':
        w = w.replace(c, '')

    return w.strip()


if __name__ == '__main__':
    while 1:
        try:
            test(raw_input())
        except SyntaxError:
            wikipedia.stopme()
            break
