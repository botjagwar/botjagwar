from unittest.case import TestCase
from unittest.mock import MagicMock

from api.page_renderer.mg import MGWikiPageRenderer


class TestRenderers(TestCase):
    def test_head_section(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {}
        info.language = 'mg'
        info.additional_data['etymology'] = 'no etimologies for you!!'
        info.part_of_speech = 'ana'
        info.additional_data['transcription'] = ['totot', 'toto']
        head_section = renderer.render_head_section(info)
        expected = """
=={{=""" + info.language + """=}}==

{{-etim-}}
:""" + info.additional_data['etymology'] + """
{{-""" + info.part_of_speech + """-|""" + info.language + """}}
'''{{subst:BASEPAGENAME}}''' (""" + ', '.join(info.additional_data['transcription']) + """)"""
        self.assertEqual(head_section, expected)

    def test_etymology(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {'etymology': 'etimologicheski'}
        etymology = renderer.render_etymology(info)
        self.assertEqual(etymology, """
{{-etim-}}
:""" + info.additional_data['etymology'])

    def test_definitions(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.definitions = ['def2', 'def1', 'def4']
        definitions = renderer.render_definitions(info, [])
        rendered_definitions = """
# def1
# def2
# def4"""
        self.assertEqual(definitions, rendered_definitions)

    def test_definitions_with_examples(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {}
        info.definitions = ['def1', 'def2', 'def4']
        info.additional_data['examples'] = [['exdef1'], ['exdef2', 'exdef22'], ['exdef4']]
        definitions = renderer.render_definitions(info, [])
        rendered_definitions = """
# def1
#* ''exdef1''
# def2
#* ''exdef2''
#* ''exdef22''
# def4
#* ''exdef4''"""
        self.assertEqual(definitions, rendered_definitions)

    def test_definitions_with_link(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        links = ['def2', 'def1', 'ak']
        info.definitions = ['def2.', '[[def1]]', 'def4', 'mult ak']
        definitions = renderer.render_definitions(info, links)
        rendered_definitions = """
# [[def1]]
# [[def2|def2]].
# [[def4]]
# mult ak"""
        self.assertEqual(definitions, rendered_definitions)

    def test_pronunciation_non_list(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {'pronunciation': 'abcsded'}
        pronunciation = renderer.render_pronunciation(info)
        pronunciation_section = """

{{-fanononana-}}
* abcsded"""
        self.assertEqual(pronunciation, pronunciation_section)

    def test_pronunciation_list(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {'pronunciation': ['{{p1|tptp}}', '{{p1|tptp2}}']}
        pronunciation = renderer.render_pronunciation(info)
        pronunciation_section = """

{{-fanononana-}}
* {{p1|tptp}}
* {{p1|tptp2}}"""
        self.assertEqual(pronunciation, pronunciation_section)

    def test_audio_pronunciation(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {'audio_pronunciations': ['audio1.mp3']}
        info.entry = 'entry'
        pronunciation = renderer.render_pronunciation(info)
        pronunciation_section = """

{{-fanononana-}}
* {{audio|audio1.mp3|entry}}"""
        self.assertEqual(pronunciation, pronunciation_section)

    def test_ipa_pronunciation(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {'ipa': ['akakak']}
        info.entry = 'entry'
        info.language = 'mg'
        pronunciation = renderer.render_pronunciation(info)
        pronunciation_section = """

{{-fanononana-}}
* {{fanononana|akakak|mg}}"""
        self.assertEqual(pronunciation, pronunciation_section)

    def test_synonyms(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {'synonyms': ['syn1']}
        synonyms = renderer.render_synonyms(info)
        sections = """

{{-dika-mitovy-}}
* [[syn1]]"""
        self.assertEqual(synonyms, sections)

    def test_antonyms(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {'antonyms': ['ant1']}
        synonyms = renderer.render_antonyms(info)
        sections = """

{{-dika-mifanohitra-}}
* [[ant1]]"""
        self.assertEqual(synonyms, sections)

    def test_related_terms(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {'related_terms': ['rt1']}
        synonyms = renderer.render_related_terms(info)
        sections = """

{{-teny mifandraika-}}
* [[rt1]]"""
        self.assertEqual(synonyms, sections)

    def test_derived_terms(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {'derived_terms': ['rt1']}
        synonyms = renderer.render_related_terms(info)
        sections = """

{{-teny mifandraika-}}
* [[rt1]]"""
        self.assertEqual(synonyms, sections)

    def test_section(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {'test_attribute': 'toskjf'}
        section = renderer.render_section(info, '{{-test-header-}}', 'test_attribute')
        self.assertIn('{{-test-header-}}', section)

    def test_further_reading(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {'further_reading': ''}
        further_reading = renderer.render_further_reading(info)
        self.assertIn('{{-famakiana fanampiny-}}', further_reading)

    def test_references(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.additional_data = {'references': ['']}
        references = renderer.render_references(info)
        self.assertIn('{{-tsiahy-}}', references)

    def test_delete_section_bottom(self):
        renderer = MGWikiPageRenderer()
        test_wikipage = """=={{=pt=}}==

{{-etim-}}
: {{vang-etim|pt}}


{{-ana-|pt}}
'''sapo''' 
# [[ankalan-damira]]
# [[bakaka]]
# [[sabakaka]]
# [[saobakaka]]

=={{=es=}}==

{{-etim-}}
: {{vang-etim|es}}


{{-ana-|es}}
'''sapo''' 
# [[ankalan-damira]]
# [[bakaka]]
# [[sabakaka]]
# [[saobakaka]]
"""
        expected = """=={{=pt=}}==

{{-etim-}}
: {{vang-etim|pt}}


{{-ana-|pt}}
'''sapo''' 
# [[ankalan-damira]]
# [[bakaka]]
# [[sabakaka]]
# [[saobakaka]]

"""
        removed_section = renderer.delete_section('es', test_wikipage)
        self.assertEqual(removed_section, expected)

    def test_delete_section_top(self):
        renderer = MGWikiPageRenderer()
        test_wikipage = """=={{=pt=}}==

{{-etim-}}
: {{vang-etim|pt}}


{{-ana-|pt}}
'''sapo''' 
# [[ankalan-damira]]
# [[bakaka]]
# [[sabakaka]]
# [[saobakaka]]

=={{=es=}}==

{{-etim-}}
: {{vang-etim|es}}


{{-ana-|es}}
'''sapo''' 
# [[ankalan-damira]]
# [[bakaka]]
# [[sabakaka]]
# [[saobakaka]]
"""
        expected = """
=={{=es=}}==

{{-etim-}}
: {{vang-etim|es}}


{{-ana-|es}}
'''sapo''' 
# [[ankalan-damira]]
# [[bakaka]]
# [[sabakaka]]
# [[saobakaka]]
"""
        removed_section = renderer.delete_section('pt', test_wikipage)
        self.assertEqual(removed_section, expected)

    def test_delete_section_middle(self):
        renderer = MGWikiPageRenderer()
        test_wikipage = """
=={{=es=}}==

{{-mat-|es}}
'''valer''' 
# [[+''''de''']]
# [[manampy]] na manan-danja
# ny ho [[matanjaka]]
# ny ho [[mendrika]]
# ny ho [[salama]] [[tsara]]

{{-tsiahy-}}
{{wikibolana|en|valer}}

=={{=fro=}}==

{{-mat-|fro}}
'''valer''' 
# [[midina]]

{{-tsiahy-}}
* {{Tsiahy:Godefroy}}
* {{Tsiahy:Anglo-Norman On-Line Hub}}
* {{wikibolana|en|valer}}

=={{=gl=}}==

{{-mat-|gl}}
'''valer''' 
# [[manampy]]
# [[mifanaraka]] amin'ny
# ny ho azo [[ekena]]
# ny ho [[mendrika]]

{{-fanononana-}}
* {{IPA|gl|[baˈleɾ]}}

{{-tsiahy-}}
* {{Tsiahy:gl:DDGM}}
* {{Tsiahy:gl:CX}}
* {{Tsiahy:gl:DDLG}}
* {{Tsiahy:gl:TILG}}
* {{Tsiahy:TLPGP}}
* {{wikibolana|en|valer}}        
"""
        expected = """
=={{=es=}}==

{{-mat-|es}}
'''valer''' 
# [[+''''de''']]
# [[manampy]] na manan-danja
# ny ho [[matanjaka]]
# ny ho [[mendrika]]
# ny ho [[salama]] [[tsara]]

{{-tsiahy-}}
{{wikibolana|en|valer}}


=={{=gl=}}==

{{-mat-|gl}}
'''valer''' 
# [[manampy]]
# [[mifanaraka]] amin'ny
# ny ho azo [[ekena]]
# ny ho [[mendrika]]

{{-fanononana-}}
* {{IPA|gl|[baˈleɾ]}}

{{-tsiahy-}}
* {{Tsiahy:gl:DDGM}}
* {{Tsiahy:gl:CX}}
* {{Tsiahy:gl:DDLG}}
* {{Tsiahy:gl:TILG}}
* {{Tsiahy:TLPGP}}
* {{wikibolana|en|valer}}        
"""
        removed_section = renderer.delete_section('fro', test_wikipage)
        self.assertEqual(removed_section, expected)

