# -*- coding: utf-8  -*-
import re, os, time
import pywikibot as wikipedia
import pywikibot.xmlreader as Xmlreader
from dikantenyvaovao import Translation, entryprocessor, setThrottle
import DLscript

from modules import output

class NoWordException(Exception):
    def __init__(self):
        pass


class PageObject(object):
    def __init__(self, title, content=u"", site="wiktionary", lang="mg"):
        self.lang = lang
        self.site = site        
        self.title = unicode(title)
        self.content = u""
                
    def download(self):
        Page = self.get_WikiPageObject()
        if Page.exists():
            try:    
                self.content = Page.get()
            except Exception:
                self.content = u""
        else:
            self.content = u""
            
    def upload(self, comment="manavao pejy"):
        Page = self.get_WikiPageObject()
        tries = 0
        while 1:
            try:
                self.content = Page.put(self.content, comment)
                break
            except wikipedia.exceptions.PageNotSaved:
                self.content = u""
                if tries<5:
                    time.sleep(10)
                    tries += 1
                    continue
                else:
                    break
    
    def __repr__(self):
        return "PageObject{%s}"%self.title
                
    def get_WikiPageObject(self):
        return wikipedia.Page(wikipedia.getSite(self.lang, self.site), self.title)
        


class PageFinder(object):
    def __init__(self, dump_filename):
        xmlfile = Xmlreader.XmlDump(dump_filename)
        self.pageobjects = {}
        i = 0
        
        for entry in xmlfile.parse():
            i += 1
            if not i%1000: 
                print str(i) + (len(str(i)) + 1)*chr(8),
            if entry.ns!=0: continue 
            self.pageobjects[entry.title] = PageObject(entry.title, entry.text)
                         
    
    def find(self, pagetitle):
        if self.pageobjects.has_key(pagetitle):
            return self.pageobjects[pagetitle]
        else:
            return False



class BaseDumpProcessor(object):
    def load(self, dumptype, filename, language):
        if dumptype == 'dump':
            self.load_dump(u"data/"+filename, language)
        elif dumptype == 'titles':
            self.load_titlefile(u"data/"+filename, language)
            self.process = self.process_titlelist

    def load_dump(self, filename, language='en'):
        self.language = language
        self.file = Xmlreader.XmlDump(filename)

    def load_titlefile(self, filename, language='en'):
        self.language = language
        self.file = file(filename,'r').readlines()
        self.wprocessor = self.processor.process_wiktionary_page

    def process_titlelist(self, wantedcount=0):
        page_generated = 0
        count = 0
        for entry in self.file.readlines():
            count += 1
            if count<wantedcount:
                continue
            print count
            Page = wikipedia.Page(wikipedia.getSite(self.language, 'wiktionary'), entry.title)
            page_generated += self.processor(self.language, Page)




class Translation_finder_in_dump(BaseDumpProcessor):
    def __init__(self, language='en'):
        self.dumpfile = None
        self.list_translations = []
        self.newentries = []
        self.processor = Translation()
        self.language = language
        self.output = output.Output()
        self.allwords = self.processor.get_allwords()
        self.alltranslations = {}
        self.langblacklist = ['fr','en','sh','de','zh']
        self.wprocessor = self.processor.process_wiktionary_page
        
        print len(self.allwords)       
        


    def get_alltranslations(self, language='en'):
        alldata = self.sql_db.read({'fiteny':language})
        ret = {}
        for data in alldata:
            if ret.has_key(data[1]):
                ret[data[1]] = unicode(data[3], 'latin1')
            else:
                ret[data[1]] = unicode(data[3], 'latin1')
        return ret

        
    def process(self, wantedcount, recover=False):
        def target_redir(Page):
            if not Page.isRedirectPage():
                return Page
            else:
                return target_redir(Page.redirectTarget())
        
        count = i = 0
        wiktprocessors = {'en':entryprocessor.process_enwikt,
                          'fr':entryprocessor.process_frwikt}
        
        p = wiktprocessors[self.language]()
        newentries = {}
        charconv = {u"ÃÂ ": u"à", u"ÃÂÃÂ´": u"ô", u"ÃÂ±": u"ñ", u"ÃÂÃÂ¢": u"à", u"ÃÂÃÂ®": "i"}
        for fileentry in self.file.parse():
            i+=1
            if i<wantedcount:
                continue
            Page = wikipedia.Page(wikipedia.getSite('mg', 'wiktionary'), fileentry.title)
            
            p.set_text(fileentry.text)
            p.process(Page)
            entries = p.getall()
            
            for entry in entries:
                if entry[2] in self.langblacklist: #check in language blacklist
                    continue          
                try:
                    frentry = entry[3].split("#")[0]
                    mg_translation = self.alltranslations[frentry]
                    for char in charconv:
                        mg_translation = mg_translation.replace(char, charconv[char])
                except Exception:
                    continue
                infos = {
                    'entry': entry[0],
                    'POS':  entry[1],
                    'definition': mg_translation,
                    'lang': entry[2],
                    'olang': self.language,
                    'origin': frentry}
                    
                page_c = infos
                newentries[infos['entry']] = page_c
                count += 1
                if not count%100: 
                    print count, "/", i
                    wikipedia.output("%(entry)s [%(lang)s]-> %(origin)s -> %(definition)s"%infos)
                
        for e in newentries:
            try:
                if (self.processor.exists(newentries[e]['lang'], newentries[e]['entry']) 
                    or not (type(newentries[e]) is dict)):
                    continue
            except Exception:
                continue
            cpage = self.output.wikipage(newentries[e])
            mgpage = wikipedia.Page(wikipedia.getSite('mg', 'wiktionary'), e)
            page_c = newentries[e]

            page_OK = False
            try:
                page_OK = mgpage.exists() and not mgpage.isRedirectPage()
            except Exception:
                continue

            if page_OK:
                page_c = mgpage.get()
                if page_c.find(u"{{-%(POS)s-|%(lang)s}}"%infos) == -1:
                    re.sub("==[ ]?\{\{=%s=\}\}[ ]?=="%infos['lang'], 
                             cpage,  page_c)
                    newentries[infos['entry']] = page_c
                    count += 1
            else:
                page_c = cpage
            try:
                mgpage.put_async(page_c, "+pejy vaovao avy amin'ny dump")
                self.output.db(newentries[e])
            except Exception:
                continue
            

    def run(self, in_file, language, count):
        setThrottle(1)
        #in_file = raw_input("rakitra? >")#'enwiktionary-20131202-pages-meta-current.xml.bz2'            
        #language = raw_input("fitenin'ny wiki nangalana ilay dump >")
        #count = int(raw_input('laharana hanombohana >'))            
        self.alltranslations = self.processor.get_alltranslations(language)
        self.load('dump', in_file, language)
        self.process(0)



def main():
    #o = PageFinder("data/enwiktionary-20131202-pages-meta-current.xml.bz2")
    #wikipedia.output(o.find(u"puffy"))
    #DLscript.DownloadURL(u"http://dumps.wikimedia.org/frwiktionary/latest/frwiktionary-latest-pages-meta-current.xml.bz2", u"data/frwiktionary-latest-pages-meta-current.xml.bz2", True)
    #DLscript.DownloadURL(u"http://dumps.wikimedia.org/enwiktionary/latest/enwiktionary-latest-pages-meta-current.xml.bz2", u"data/enwiktionary-latest-pages-meta-current.xml.bz2", True)
    bot = Translation_finder_in_dump()
    #bot.run(u"frwikttest.xml", u"fr", 0)
    #bot.run(u"frwiktionary-latest-pages-meta-current.xml.bz2", u"fr", 0)
    bot.run(u"enwiktionary-latest-pages-meta-current.xml.bz2", u"en", 0)
    
if __name__ == '__main__':
    try:
        main()
    finally:
        wikipedia.stopme()
