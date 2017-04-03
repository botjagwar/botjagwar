# (c) RAMAROJAONA Rado
import re
import pywikibot as wikipedia

def ProcessWikt(language):
    return eval("process_%swikt()"%language)

class wiktprocessor(object):
    """Mother class of all Wiktionary page processors"""
    def __init__(self, test=False, verbose=False):
        self.content = None
        self.Page = None

    def process(self, page):
        self.Page = page
        try:
            #print type(page)
            if (type(page) is unicode) or (type(page) is str):
                self.content = page
            else:
                self.content = page.get()
        except wikipedia.exceptions.NoPage:
            print "Tsy misy ilay pejy"
            self.content = u""
        except wikipedia.exceptions.IsRedirectPage:
            print "Pejy fihodinana ilay pejy"
            self.content = u""
        except Exception:
            print 'Hadisoana'
            self.content = u""

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
        #print templatestr, parameterstr
        RET_text = u""
        templates_withparams = self.Page.templatesWithParams()
        for template in templates_withparams:
            if template[0].title() == templatestr:
                for params in template[1]:
                    if params.startswith(parameterstr+u'='):
                        RET_text = params[len(parameterstr)+1:]
        return RET_text

    def getall(self, keepNativeEntries=False):
        POStran = {u"värb":'mat',
                   u'subsat':'ana',
                   u'ladyek':'mpam-ana'}
        
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
    def __init__(self):
        wiktprocessor.__init__()
        try:
            f = file('data/plwikt_langdata.dct','r').read()
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
                ret.append( (language, translation) )
        return ret


    def _get_translation_lines(self, page_c):
        ret = []
        # getting borders of translation section
        tr_start = page_c.find(u"== polski ({{język polski}}) ==")+len(u"== polski ({{język polski}}) ==")
        if page_c.find(u"{{tłumaczenia}}", tr_start)!=-1:
            tr_start = page_c.find(u"{{tłumaczenia}}", tr_start)
        else: return ret     
        if page_c.find(u"{{źródła}}", tr_start)!=-1:
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
        
    
    def retrieve_translations(self, page_c): # Needs updating
        """Fampirimana ny dikanteny azo amin'ny alalan'ny REGEX araka ny laharan'ny Abidy"""
        ret = []
        if page_c.find('{{}} :')==-1:return ret
        trads = re.findall("# (.*) : \[\[(.*)\]\]", page_c)
        trads.sort()
        tran = re.sub("# (.*) : \[\[(.*)\]\]", '', page_c)
        tran = tran.strip('\n')
        trstr = '{{}} :'
        tran = tran.replace('{{}} :', '')
        if len(trads)>200:
            print 'hadisoana ?'
            return tran
        for i in trads:
            trstr = trstr.replace("{{}} :","# %s : [[%s]]\n{{}} :"%i)
            ret.append(i)
            
        return ret

    def getall(self, keepNativeEntries=False):
        items = []
        for lang in re.findall('\{\{\-([a-z]{3,7})\-\|([a-z]{2,3})\}\}',self.content):
            # word DEFINITION Retrieving
            d1 = self.content.find("{{-%s-|%s}}"%lang)+len("{{-%s-|%s}}"%lang)
            d2 = self.content.find("=={{=", d1)+1 or self.content.find("== {{=", d1)+1
            if d2: definition = self.content[d1:d2]
            else: definition = self.content[d1:]
            try:
                definition = definition.split('\n# ')[1]
            except IndexError:
                print " Hadisoana : Tsy nahitana famaritana"
                continue
            if (definition.find('\n')+1):
                definition = definition[:definition.find('\n')]
                definition = re.sub("\[\[(.*)#(.*)\|?\]?\]?", "\\1", definition)
            definition = stripwikitext(definition)
            if not definition: continue

            else:
                i = (lang[0].strip(), #POS
                     lang[1].strip(), #lang
                     definition)
                items.append(i)
                #wikipedia.output(u" %s --> %s : %s"%i)
        #print "Nahitana dikanteny ", len(items) ", len(items)
        return items
        

class process_frwikt(wiktprocessor):
    def __init__(self,  test=False, verbose=False):
        self.content = None
        self.postran ={
            'verb':'mat',
            'adj':'mpam-ana',
            'nom':'ana',
            'adv':'tamb',
            'pronom':'solo-ana',
            u'préf':'tovona',
            'suf':'tovana'
            }
            

    def retrieve_translations(self, page_c):
        retcontent =  []
        regex = '\{\{trad[\+\-]+?\|([A-Za-z]{2,3})\|(.*?)\}\}'
        for entry in re.findall(regex, page_c):
            for x in "();:.,":
                if entry[1].find(x)!=-1:
                    continue
                if entry[1].find('|')!=-1:
                    langcode = entry[0]
                    entree = entry[1][:entry[1].find('|')]
                    entree = entree.decode('utf8')

                    entry = (langcode, entree) # (codelangue, entree)
            try:
                entree = unicode(entry[1])
            except UnicodeDecodeError:
                entree = unicode(entry[1], 'latin1')
                
            retcontent.append(entry)


    def getall(self, keepNativeEntries=False):
        """languges sections in a given page formatting: [(POS, lang, definition), ...]"""
        items=[]

        if self.content is None:
            raise Exception("self.page tsy voafaritra. self.process() tsy mbola nantsoina")

        # mandrapahatapitry ny fanovana ny zana-pizarana ho zana-pizarana azo ovaina
        for lang in re.findall('\{\{\-([a-z]+)\-\|([a-z]{2,3})\}\}',self.content):
            #print lang, 1
            # word DEFINITION Retrieving
            d1 = self.content.find("'{{-%s-|%s}}"%lang)+len("'{{-%s-|%s}}"%lang)
            d2 = self.content.find("=={{langue|", d1)+1 or self.content.find("== {{langue|", d1)+1
            if d2: definition = self.content[d1:d2]
            else: definition = self.content[d1:]
            try:
                definition = definition.split('\n# ')[1]
            except IndexError:
                #print " Hadisoana : Tsy nahitana famaritana"
                continue
            if (definition.find('\n')+1):
                definition = definition[:definition.find('\n')]
                definition = re.sub("\[\[(.*)#(.*)\|?\]?\]?", "\\1", definition)
            definition = stripwikitext(definition)
            if not definition: continue

            if lang[1].strip()=='fr':
                pass
            else:
                i = (lang[0].strip(), #POS
                     lang[1].strip(), #lang
                     definition)
                items.append(i)
                #wikipedia.output(u" %s --> %s : %s"%i)


        for lang in re.findall('\{\{S\|([a-z]+)\|([a-z]{2,3})\}\}',self.content):
            #print lang, 2
            # word DEFINITION Retrieving
            d1 = self.content.find("'{{S|%s|%s}}"%lang)+len("{{S|%s|%s}}"%lang)
            d2 = self.content.find("=={{langue|", d1)+1 or self.content.find("== {{langue|", d1)+1
            if d2: definition = self.content[d1:d2]
            else: definition = self.content[d1:]
            try:
                definition = definition.split('\n# ')[1]
            except IndexError:
                #print " Hadisoana : Tsy nahitana famaritana"
                continue
            if (definition.find('\n')+1):
                definition = definition[:definition.find('\n')]
                definition = re.sub("\[\[(.*)#(.*)\|?\]?\]?", "\\1", definition)
            definition = stripwikitext(definition)
            if not definition: continue

            if lang[1].strip()=='fr':
                pass
            else:
                i = (lang[0].strip(), #POS
                     lang[1].strip(), #lang
                     definition)
                items.append(i)
                #wikipedia.output(u" %s --> %s : %s"%i)
        
        ##print "Nahitana dikanteny ", len(items)
        return items



class process_enwikt(wiktprocessor):
    def __init__(self, test=False, verbose=False):
        self.__init__
        self.test=test
        self.postran={
            'Verb':'mat',
            'Adjective':'mpam-ana',
            'Noun':'ana',
            'Adverb':'tamb',
            'Pronoun':'solo-ana',
            'Prefix':'tovona',
            'Suffix':'tovana'
            }
        self.verbose=verbose
        
        self.code={}
        dictfile=file('data/languagecodes.dct','r')
        f = dictfile.read()
        try:
            self.code = eval(f)
        except SyntaxError:
            pass
        finally:
            dictfile.close()

    def lang2code(self, l):
        return self.code[l]


    def retrieve_translations(self, page_c):
        """Maka ny dikanteny ao amin'ny pejy iray"""
        retcontent = []
        page_c= page_c.encode('utf8')
        regex = '\{\{t[\+\-]+?\|([A-Za-z]{2,3})\|(.*?)\}\}'
        for entry in re.findall(regex, page_c):
            for x in "();:.,":
                if entry[1].find(x)!=-1:
                    continue
                if entry[1].find('|')!=-1:
                    langcode = entry[0]
                    entree = entry[1][:entry[1].find('|')]
                    entree = entree.decode('utf8')

                    entry = (langcode, entree) # (codelangue, entree)
            try:
                entree = unicode(entry[1])
            except UnicodeDecodeError:
                entree = unicode(entry[1], 'latin1')
                
            retcontent.append(entry)
        try:
            retcontent.sort()
        except UnicodeError:
            pass
        
        #print "Nahitana dikanteny ", len(retcontent)
        return retcontent # liste( (codelangue, entrée)... )


    def getall(self):
        items=[]
        c = self.content

        #famafana ny etimilojia
        c = re.sub('Etymology','',c)
         
        for l in re.findall("[\n]?==[ ]?([A-Za-z]+)[ ]?==\n",c):
            c = c[c.find('==%s=='%l):]
                
            #pos
            pos=''
            ptext=regex_ptext=''
            for p in self.postran:
                regex_ptext += '%s|'%p
            regex_ptext=regex_ptext.strip('|')
            #defsectg = '\n(={4}[ ]?%s[ ]?={4})\n'%regex_ptext
            ptext='\n={4}[ ]?(%s)[ ]?={4}\n'%regex_ptext
            if re.search(ptext, c) is None:
                #defsectg = '\n(={3}[ ]?%s[ ]?={3})\n'%regex_ptext
                ptext='\n={3}[ ]?(%s)[ ]?={3}\n'%regex_ptext
            posregex = re.findall(ptext,c)

            c = re.sub('\[\[(.*)#English\|(.*)\]\]','\\1', c)
            c = re.sub('\[\[(.*)\|(.*)\]\]','\\1', c)

            #definition
            try:
                defin = c.split('\n#')[1]
                if defin.find('\n')!=-1:
                    defin = defin[:defin.find('\n')]
            except IndexError:
                if self.verbose: print "Hadisoana indexerror."
                continue
            defin = re.sub("\((.*)\)","",defin).strip()
            defin = re.sub("\{\{(.*)\}\}","",defin).strip()

            defin = re.sub("\[\[(.*)#(.*)\|?[.*]?\]?\]?", "\\1", defin)

            for char in '[]':
                defin=defin.replace(char,'')

            defins = defin.split(',')
            
            
            if len(defins)>1:
                defin = defins[0]

            #print ptext
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
                if self.verbose: print "Tsy nahitana dikan'ny karazan-teny %s"%pos
                continue
            if defin.startswith('to ') or defin.startswith('To '):
                pos = 'mat'
                defin = defin[2:]
            elif defin.startswith('a ') or defin.startswith('A '):
                pos = 'ana'
                defin = defin[1:]
            if len(defin.strip())<1: continue
            try:
                i = (pos, self.lang2code(l), defin.strip())
                if self.verbose: wikipedia.output('%s --> teny  "%s" ; famaritana: %s'%i)
                items.append(i)
            except KeyError:
                continue
            
        ##print "Nahitana dikanteny ", len(items)
        return items

def lang2code(l):
    dictfile=file('data/languagecodes.dct','r')
    f = dictfile.read()
    d = eval(f)
    dictfile.close()
    
    return d[l]
    
def test(imput=False):
    f = process_vowikt()
    p = wikipedia.Page(wikipedia.getSite('vo','wiktionary'), imput)
    f.process(p)
    print f.getall()

def stripwikitext(w):
    w=re.sub('[ ]?\[\[(.*)\|(.*)\]\][ ]?','\\1', w)
    w=w.replace('.','')
    w=re.sub('[ ]?\{\{(.*)\}\}[ ]?','',w)
    for c in '[]':
        w=w.replace(c,'')

    return w.strip()
    
            

if __name__=='__main__':
    while 1:
        try:
            test(raw_input())
        except SyntaxError:
            wikipedia.stopme()
            break
