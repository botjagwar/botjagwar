import pywikibot
import re
from datetime import datetime
stats_page = pywikibot.Page(pywikibot.Site('mg', 'wiktionary'), 'Mpikambana:Bot-Jagwar/Lisitry ny Wikibolana/tabilao')
revisions = stats_page.revisions()

revisions = [(revision.timestamp, revision.revid) for revision in revisions]
out_file = open('wikistats.csv', 'w')
for revision in revisions:
    data = stats_page.getOldVersion(revision[1])
    lines = data.split('\n')

    # Output:
    line = [line for line in lines if '//mg.wiktionary.org/w/api.php?action=query&meta=siteinfo&format=xml&siprop=statistics' in line][0]
    article = re.findall('\{\{formatnum:([0-9]+)\}\}', line)[0]
    print(revision[0].timestamp(), article)
    out_file.write(f'{revision[0].timestamp()},{article}\n')
