import pywikibot as wikipedia
import re,ircbot,random,time

class IRC_RC_Bot(ircbot.SingleServerIRCBot):
    def __init__(self, user="BotJagwarIRCCleanup_ID%x"%random.randint(1,0xffff)):
        self.langs=[]
 
        self.stats={'edits':0.0,'newedits':0.0,'errors':0.0}
        
        print "\n---------------------\n       PARAMETATRA : "

        self.channel = "#mg.wiktionary"
        self.botname=user
        
        ircbot.SingleServerIRCBot.__init__(self, [("irc.wikimedia.org", 6667)],
                                           self.botname,
                                           "Robo an'i Jagwar.")
        print "Init OK."
    def on_welcome(self, serv, ev):
        serv.join("#mg.wiktionary")

    def on_kick(self, serv, ev):
        serv.join("#mg.wiktionary")
        
    def on_pubmsg(self, serv, ev):
        message = ev.arguments()[0].decode('utf8')
        message = re.sub('\x03[0-9]{2}','',message)
        # Fijerena ny teny iditra.
        print " (%s/%s/%s GMT %s:%s) fanovana vaovao"%tuple(time.gmtime()[0:5])
        try:
            wikipedia.output(message)
            item = re.search('\[\[(.*)\]\]',message).groups()[0]
            Page = wikipedia.Page('mg',item)
            #print "fanovana faha-%d"%(self.stats['edits']+1)
            self.stats['edits']+=1.
            self.stats['newedits']+= cleanup(Page)
            self.stats['rend']=100.* self.stats['errors']/self.stats['edits']
            self.stats['rendpejy']=100.* float(self.stats['newedits'])/self.stats['edits']
            if self.stats['edits']>=1:
                wikipedia.output("""
#################################
\03{white}statistika\03{default}    
#################################
""")
                wikipedia.output("fanovana %(edits)s\nfamoronana pejy %(newedits)s\nhadisoana %(errors)s\n\ntahan-kadisoana: %(rend).2f isanjato \ntaham-pamoronana %(rendpejy).2f  isanjato \n"%self.stats)

            print "Vita ny asa amin'ilay pejy."
        except SyntaxError as ex :
            self.stats['errors']+=1
            errstr = u'Hadisoana : ' + ex.message + u'\n'
            file('autocleanup.exceptions','a').write(errstr)

def IRCcleanup():
    while 1:
        try:
            bot = IRC_RC_Bot()
            bot.start()
        except KeyboardInterrupt:
            print "Najanona tamin'ny alalan'i CTRL+C"
            break
        except Exception:
            time.sleep(10)
            del bot
            continue

    wikipedia.stopme()

def cleanup_withfile():
    dictfile={}
    for item in file('existingpages.txt','r').readlines():
        p = item.split('->')[0].strip().decode('utf8')
        try:
            dictfile[p]+=1
        except KeyError:
            dictfile[p]=0
            dictfile[p]+=1
    pagelist=[]
    for key in dictfile:
        if dictfile[key]>1: pagelist.append( (dictfile[key], key) )
    pagelist.sort()
    pagelist.reverse()
    i=0
    for page in pagelist: #page : tuple(int, str)
        i+=1
        print "page hovaina faha-%d -- ; teny iditra %d ; pejy hovaina : %d "%(i,page[0],len(pagelist)-i)
        if not len(page[1]): continue
        Page=wikipedia.Page('mg',page[1])
        cleanup(Page)
            
    

def cleanup(Page, put=True):
    summary=u"[[Wiktionary:Firafitry ny teny iditra|Firafetana ho azy]]"
    if Page.exists():
        c = orig = Page.get()
    else: return 0
    c = alphasort(c)

    if c==orig: return 0
    else:
        wikipedia.showDiff(orig,c)
        if put:
            Page.put(c, summary)
        return 1
    

def alphasort(c):
    """Mifantina ny teny iditra araka ny laharan'ny abidy"""
    entries = []
    iwikis = re.findall("\[\[(.*):(.*)\]\]",c)
    c = re.sub("\[\[(.*):(.*)\]\]","",c)
    while (c.find('\n\n')!=-1): c=c.replace('\n\n','\n')
    t = retstr = u""
    c = re.sub("==[ ]?\{\{=([a-z\-]+)=\}\}[ ]?==","=={{=\\1=}}==",c)
    langs = re.split("(==[ ]?\{\{=[a-z\-]+=\}\}[ ]?==)",c)
    i=0
    if len(langs[0])<=5: del langs[0]
    #print langs
    for lang in langs:
        i+=1
        if i%2:
            l = lang
        else:
            cont = lang
            entries.append( (l, cont) )
            
    iwikis.sort()
    entries.sort()
    for entry in entries:
        r = entry[0] + u''
        r += entry[1] + u'\n\n'
        if entry[0]=='=={{=mg=}}==': retstr = r + u'\n' + retstr
        else: retstr = retstr + '\n' + r            

    retstr += u"\n"
    for iw in iwikis:
        retstr += "[[%s:%s]]\n"%iw
    while (retstr.find('\n\n\n')!=-1): retstr=retstr.replace('\n\n\n','\n')

    return retstr

def replacetemplate(c):
    """Manolo ny endrika mba ho endrika amin'ny teny malagasy (ho an'ireo teny nodikaina avy amin'ny wiki vahiny ireo indrindra indrindra"""
    tem = {
        '-nom-':'-ana-',
        '-adj-':'-mpam-ana',
        '-verb-':'-mat-',
        '-adv-':'-tamb-',
        '-pref':'-tovona-',
        '-suf-':'-tovana-'}
    
    for t in tem:
        c = c.replace('{{-%s-|'%t,'{{-%s-|'%tem[t])
    return c

if __name__=='__main__':
    try:
        #cleanup(wikipedia.Page('mg','blindando'))
        IRCcleanup()
        #cleanup_withfile()
    finally:
        wikipedia.stopme()
        
