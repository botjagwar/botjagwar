import urllib
import re
import htmlprocessor as hp
import BeautifulSoup


class HTMLcorpusretriever(object):
    def __init__(self, tags=['div','p'], URL="http://tiatanindrazana.com/pages/modules.php?id=10"):
        self.tags = tags
        self.Emptycount = 0
        self.URL = URL
        self.lenmax = 0
        
    def getURLDatas(self, URL):
        """Mamoaka ny zavata div, p mety ahitana zavatra"""
        URLdata = urllib.urlopen(URL).read()
        print("Lanjam-pejy : %d oktety" % len(URLdata))
        if re.search(r'<title>(.*)</title>', URLdata).group() is None: return
        try:
            titlestr = re.search(r'<title>(.*)</title>', URLdata).group()
        except Exception:
            return
        title = hp.strip_tags(titlestr)

        for tag in self.tags:                
            for divdata in re.findall('<%s>(.*)</%s>'%(tag,tag), URLdata):
                divdata = hp.strip_tags(divdata)
                yield (title, divdata, URL)


class NewsSiteRetriever(HTMLcorpusretriever):
    def __init__(self, site):
        super(NewsSiteRetriever, self).__init__(URL=site)
        self.site = site
        self.pagelist = []
        
    def run(self):
        pass
    
    def getlinks(self):
        content = urllib.urlopen(self.site).read()
        return re.findall("<a href=\"(.*)\" [a-z]+", content)
        

def mainURL(URL):
    """ Aza adino ny mametraka "http://" """
    return re.search('http://(.*?)/(.*?)', URL).group()
