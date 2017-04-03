# -*- coding: utf-8 -*-

import os, re

import HTMLParser, BeautifulSoup

class MLStripper(HTMLParser.HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)



class NewWordFinder(object):

    def __init__(self, existinglist, corpus):
        assert type(existinglist) is list
        assert type(corpus) is unicode

        self.existing = existinglist
        self.corpus = corpus

    def run(self, pagetitle=u""):
        import pywikibot as wikipedia

        page = wikipedia.Page(wikipedia.getSite("mg", "wiktionary"), pagetitle)
        page.put(self.generate_page(), "Mpahita teny vaovao")

    def set_corpus(self, corpus):
        self.corpus = corpus

    def generate_page(self):
        return self.build_wikipage(self.count_occurrences())

    def count_occurences(self):
        occurrences_dict = {}
        for word, phrase in self.extract_words():
            if word in self.existing:
                continue
            if type(word) != unicode:
                word = unicode(word)

            if occurrences_dict.has_key(word):
                if occurrences_dict[word].has_key("count"):
                    occurrences_dict[word]["count"] += 1
                    occurrences_dict[word]["phrase"] = phrase
                else:
                    occurrences_dict[word]["count"] = 1
                    occurrences_dict[word]["phrase"] = phrase
            else:
                occurrences_dict[word] = {"count" : 1, "phrase" : phrase}

        return occurrences_dict


    # fangalana ny teny eo amin'ny avy amin'ilay lahatsoratry ny gazety
    def extract_words(self):
        for phrases in self.corpus.split('.'):
            if len(phrases)>1:
                phrases = phrases[0].lower()+phrases[1:]
            print "Fijerena raha malagasy ilay fehezanteny..."
            # question marks, exclamation marks sorting
            if phrases.find('?') != -1:
                phrases = phrases.split('?')[0].strip()
            elif phrases.find('!') != -1:
                phrases = phrases.split('!')[0].strip()
            os.system('cls')
            for word in phrases.split():
                # apostrophes
                if word.find("'")!=-1:
                    word = word.split("'")[0]+"'"
                # marika eo anoloan'ny teny
                if '$#,@%' in word: continue
                if word[-1]==',': word=word[:-1]
                word=word.replace("in'","i")
                #for char in 'aeo':
                #    if word[-3:] == char+"n'" : word=word[:-3]+char+"na"

                word=word.replace(',','')

                if len(word) < 4: continue
                f=0
                # soratra hafa mety hitranga ary hialana

                for char in u'</’,="()«»“”:{}>-#@$‘?;.!,`*^$&()[]{}+«»“”‟”…‘':
                    if word.find(char)!=-1:
                        f=1
                        break
                if word[-1] == "i" : word=word[:-1]+"y"
                if not f:
                    yield [word, strip_tags(phrases)]


    def build_wikipage(self, word_occurences, noccurences=1, charlim=500):
        bpage_cont = u""
        urls = {}
        domain = u""
        for word in word_occurences:
            if len(word_occurences[word]['phrase']) > charlim:
                word_occurences[word]['phrase'] = word_occurences[word]['phrase'][:charlim] + '...'
                word_occurences[word]['phrase'] = word_occurences[word]['phrase'].replace('\n',' ')

            if word_occurences[word]['occurences']>=noccurences:
                domain = find_domain(word_occurences[word]['URL'])
                cstring = "\n* <big>'''[[%s]]'''</big> (nitranga in-%d) : <i>%s.</i> <small>(<i>[%s %s]</i>, %s)</small>"%(
                    word, word_occurences[word]['occurences'],
                    word_occurences[word]['phrase'].strip(),
                    word_occurences[word]['URL'],
                    word_occurences[word]['title'],
                    domain,
                    )

                if (urls.has_key(domain)):
                    urls[domain] += 1
                else:
                    urls[domain] = 1

                #wikipedia.output(cstring)
                bpage_cont += cstring


        urlstring = u"\n\n== Tranonkala nahitana ==\n"
        for url in urls:
            urlstring = urlstring + u"* ''%s'' &ndash; teny vaovao %d\n"%(url, urls[url])

        return bpage_cont + urlstring


class WebsiteWordFinder(object):

    def __init__(self, urllist=[]):
        self.urllist = urllist
        self.word_list = self.load_word_list()

    def run(self):
        for url in self.urllist:
            #wordfinder = NewWordFinder(self.word_list, self.load_corpus(url))
            pass

    def load_corpus(self, url):
            #TODO: implement
        pass


    def load_word_list(self):
            #TODO: implement
        pass



def find_domain(url):
    url = re.sub("http[s]?:\/\/", "", url)
    url = url.split("/")[0]

    return url


def strip_tags(html):
    s = MLStripper()
    try:
        s.feed(html)
        return s.get_data()
    except Exception:
        txt = re.sub("\<p\>(.*)\</p\>", "\\1", html)
        txt =  re.sub("\<div(.*)\>(.*)\</div\>", "", txt) 
        return txt
    
## </Fanalana ny tag HTML>

def HTMLEntitiesToUnicode(text):
    """Converts HTML entities to unicode.  For example '&amp;' becomes '&'."""
    text = unicode(BeautifulSoup.BeautifulStoneSoup(text, convertEntities=BeautifulSoup.BeautifulStoneSoup.ALL_ENTITIES))
    return text

def autoretrieve():
    #TODO: implement
    pass


def main():
    #TODO: implement
    #nw = NewWordFinder()
    pass
