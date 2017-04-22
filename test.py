#coding: utf8
import pywikibot
import modules.entryprocessor


def test_entryprocessor_frwikt():
    proc = modules.entryprocessor.process_frwikt()
    page = pywikibot.Page(
        pywikibot.Site('fr', 'wiktionary'),
        "bimi")
    proc.content = """== {{langue|cao}} ==
=== {{S|étymologie}} ===
: {{ébauche-étym|cao}}

=== {{S|nom|cao}} ===
'''bimi''' {{pron|βimi|cao}}
# {{botanique|cao}} [[fruit#fr|Fruit]].

[[Catégorie:Aliments en chácobo]]

== {{langue|la}} ==
=== {{S|adjectif|la|flexion}} ===
'''bimi''' {{pron||la}}
# ''Génitif masculin et neutre singulier de'' [[bimus#la-adj|bimus]].
# ''Nominatif masculin pluriel de'' [[bimus#la-adj|bimus]].
# ''Vocatif masculin pluriel de'' [[bimus#la-adj|bimus]].

== {{langue|se}} ==
=== {{S|nom|se|flexion}} ===
'''bimi''' {{phono|bimi|se}}
# ''Génitif singulier de ''{{lien|bipmi|se}}.
# ''Accusatif singulier de ''{{lien|bipmi|se}}.

[[en:bimi]]
[[es:bimi]]
[[fi:bimi]]
[[mg:bimi]]"""
    proc.process(page)

    expected = [
        (u'bimi', 'ana', u'cao', u'fruit'),
        (u'bimi', 'mpam', u'la', u"''G\xe9nitif masculin et neutre singulier de'' bimus"),
        (u'bimi', 'ana', u'se', u"''G\xe9nitif singulier de ''")
    ]
    got = proc.getall2()

    assert got == expected

if __name__ == '__main__':
    test_entryprocessor_frwikt()
