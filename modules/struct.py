import re
import pywikibot as wikipedia

worksite = 'mg'

class Translations(object):
    def __init__ (self, word, language, translation):
        self.language = language
        self.word=word
        self.translation
        self.content = u"" #page content
    
    def __getitem__(self, index):
        if index==0:
            return self.language
        elif index==1:
            return self.translation
        elif index==2:
            return self.word
        else:
            raise IndexError("Indexes for Translation object are 0, 1 or 2 only.")

    def get(self):
        """ Maka ny dikanteny rehetran'ny votoatim-pejy."""
        Page = wikipedia.Page(wikipedia.getSite(worksite, 'wiktionary'), self.word)
        if Page.exists():
            try:
                self.content = Page.get()
            except Exception:
                self.content = u""
        
        translations = re.findall("\{\{dikan\-teny|(.*)|([a-z]+)\}\}", self.content)
        translations.sort()
        
        self.loaded_flag = False
        return translations  
    
    def put(self, entry, language=None):
        Page = wikipedia.Page(wikipedia.getSite(self.get_workingwiki, 'wiktionary'), self.word)
        wikipedia.setAction("Dikanteny vaovao: %s (%s)"%(self.translation, self.language))

    
class Entry(object):
    """General class for entries in the Malagasy Wiktionary, and perhaps for other
       Wiktionaries too, thanks to Output class"""
       
    def __init__ (self, title, language, POS, definition, etym=u'', translations=[] ):
        self.data[u'title']=title
        self.data[u'language']=language
        self.data[u'definition']=definition
        self.data[u'POS']=POS
        self.data[u'etym']=etym
        self.data[u'translations']=translations
        self.data_repr = [self.data['POS'], self.data['language'], self.data['definition']]
        
    def init_old_style(self, entry):
        assert type(entry) is tuple #old form of entryprocessor entries
        assert len(entry) >= 4
        
        self.data['language']=entry[1]
        self.data['POS']=entry[0]
        self.data['definition']=entry[2]
        self.data['title']=entry[3]
        
        self.data_repr = [self.data['POS'], self.data['language'], self.data['definition']]
        
        
    def __repr__(self):
        return u"Entry{title=%s; language=%s; definition=%s; POS=%s; etymology=%s}"%(self.title, self.language, 
                                                                                    self.definition, self.POS, self.etym)
    
    def __getitem__(self, index):
        return self.data_repr[index]
        
    def output(self): # mety hiova
        s = u"""=={{=%(language)s=}}==
{{-%(POS)s-|%(language)s}}
'''{{subst:BASEPAGENAME}}''' {{pron X-SAMPA||%(language)s}} {{pron||%(language)s}}
# %(definition)s"""%self.data
        try:
            return s
        except UnicodeDecodeError:
            return s.decode('utf8')
