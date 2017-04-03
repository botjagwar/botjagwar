# -*- coding: utf-8 -*-
import wikipedia
import BJlib
import re

class XMLdecode:
    def __init__(self, XMLtext):
        """Kilasy mamaky ny votoatim-pejy XML iray"""
        self.Text = XMLtext

    def getElementsInTag(self, tag, temp=None, cursor=0):
        """ Mamerina ny kambansoratra anaty tag iray. """
        if temp is None:
            temp= self.Text
            
        self.tag = tag
        self.TagInit = (u"<%s" %(self.tag)).encode('utf-8')
        self.TagEnd = (u"</%s>" %(self.tag)).encode('utf-8')

        Starttag = temp.find(self.TagInit) + len(self.TagInit)
        Starttag = temp.find('>', Starttag)+1
        Endtag   = temp.find(self.TagEnd, Starttag)

        return temp[Starttag:Endtag]

    def getAllInTag(self, tag):
        """ Mamerina ny kambantsoratra rehetra ao anatin'ilay  tag voambara."""
        self.TagInit = u"<%s>" %(tag)
        self.TagEnd = u"</%s>" %(tag)
        tmp_txt = self.Text
        
        texts = [self.getElementsInTag(tag)] # init texts
        dump = []
        
        while len(tmp_txt) > (len(self.TagInit)+len(self.TagEnd)):
            cursor = 0
            # detection et lecture du contenu des balises
            bni = tmp_txt.find(self.TagInit)
            bnf = tmp_txt.find(self.TagEnd, bni)
            dump.append(self.getElementsInTag(tag, tmp_txt))
			
            # ajustement du curseur
            bttag1  = tmp_txt.find(self.TagEnd)+len(self.TagEnd)
            bttag2  = tmp_txt.find(self.TagInit, bttag1)
            bttag   = len(tmp_txt[bttag1:bttag2])
            tagslen = len(self.TagInit)+len(self.TagEnd)
            cursor = bttag + tagslen + len(self.getElementsInTag(tag, tmp_txt))
			
            # troncage du texte
            tmp_txt = tmp_txt[cursor:]
        return dump

"""
# Tao hanaovana ny fanandramana tokony hajanona ohatr'izao raha tsy novainao ny fomba sy ny sokajy
try:
    import urllib
    a = urllib.urlopen("http://www.rakibolana.org/rakibolana/rss/latest").read()
    b = XMLdecode(a).getAllInTag('item')
    print b
except KeyboardInterrupt:
    import sys
    sys.exit()
"""
