import requests
import json

# Throwaway code.

def get_list():
     lines = file('user_data/dikantenyvaovao/fr-mg', 'r').readlines()
     existing_translations = requests.get('http://localhost:8000/dictionary/fr/mg')
     data = existing_translations.json()
     wordlist = set(q for q, _ in data)
     count = 0
     lines = set(lines)
     for m in lines :
         m = m.decode('utf8')

         entries = m.split('\t')
         m2 = entries[1].strip()

         for translation in m2.split(u','):
             frword = entries[0].strip()
             if frword not in wordlist:
                 count += 1
                 data = {
                     'word': frword,
                     'translation': translation.strip(),
                     'POS': u'',
                     'dryrun': False
                 }
                 resp = requests.put('http://localhost:8000/translate/fr', data=json.dumps(data))
                 if not count % 100:
                     print '#' + count + ' dong dong'

get_list()
