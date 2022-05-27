from unittest.case import TestCase
from unittest.mock import MagicMock

from api.page_renderer.mg import MGWikiPageRenderer


class TestRenderers(TestCase):
    def test_head_section(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.language = 'mg'
        info.etymology = 'no etimologies for you!!'
        info.part_of_speech = 'ana'
        info.transcription = ['totot', 'toto']
        head_section = renderer.render_head_section(info)
        expected = """=={{=""" + info.language + """=}}==

{{-etim-}}
:""" + info.etymology + """
{{-""" + info.part_of_speech + """-|""" + info.language + """}}
'''{{subst:BASEPAGENAME}}''' (""" + ', '.join(info.transcription) + """)"""
        self.assertEquals(head_section, expected)

    def test_etymology(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.etymology = 'etimologicheski'
        etymology = renderer.render_etymology(info)
        self.assertEquals(etymology, """
{{-etim-}}
:""" + info.etymology)

    def test_definitions(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.definitions = ['def2', 'def1', 'def4']
        definitions = renderer.render_definitions(info, '', [])
        rendered_definitions = """
# def1
# def2
# def4"""
        self.assertEquals(definitions, rendered_definitions)

    def test_definitions_with_examples(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.definitions = ['def1', 'def2', 'def4']
        info.examples = [['exdef1'], ['exdef2', 'exdef22'], ['exdef4']]
        definitions = renderer.render_definitions(info, '', [])
        rendered_definitions = """
# def1
#* ''exdef1''
# def2
#* ''exdef2''
#* ''exdef22''
# def4
#* ''exdef4''"""
        self.assertEquals(definitions, rendered_definitions)

    def test_definitions_with_link(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        links = ['def2', 'def1', 'ak']
        info.definitions = ['def2.', '[[def1]]', 'def4', 'mult ak']
        definitions = renderer.render_definitions(info, '', links)
        rendered_definitions = """
# [[def1]]
# [[def2|def2]].
# [[def4]]
# mult ak"""
        self.assertEquals(definitions, rendered_definitions)

    def test_pronunciation_non_list(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.pronunciation = 'abcsded'
        pronunciation = renderer.render_pronunciation(info)
        pronunciation_section = """

{{-fanononana-}}"""
        self.assertEquals(pronunciation, pronunciation_section)

    def test_pronunciation_list(self):
            renderer = MGWikiPageRenderer()
            info = MagicMock()
            info.pronunciation = ['{{p1|tptp}}']
            pronunciation = renderer.render_pronunciation(info)
            pronunciation_section = """

{{-fanononana-}}"""
            self.assertEquals(pronunciation, pronunciation_section)

    def test_audio_pronunciation(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.entry = 'entry'
        info.audio_pronunciations = ['audio1.mp3']
        pronunciation = renderer.render_pronunciation(info)
        pronunciation_section = """

{{-fanononana-}}
* {{audio|audio1.mp3|entry}}"""
        self.assertEquals(pronunciation, pronunciation_section)

    def test_ipa_pronunciation(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.entry = 'entry'
        info.ipa = ['akakak']
        info.language = 'mg'
        pronunciation = renderer.render_pronunciation(info)
        pronunciation_section = """

{{-fanononana-}}
* {{fanononana|akakak|mg}}"""
        self.assertEquals(pronunciation, pronunciation_section)

    def test_synonyms(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.synonyms = ['syn1']
        synonyms = renderer.render_synonyms(info)
        sections = """

{{-dika-mitovy-}}
* [[syn1]]"""
        self.assertEquals(synonyms, sections)

    def test_antonyms(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.antonyms = ['ant1']
        synonyms = renderer.render_antonyms(info)
        sections = """

{{-dika-mifanohitra-}}
* [[ant1]]"""
        self.assertEquals(synonyms, sections)

    def test_related_terms(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.related_terms = ['rt1']
        synonyms = renderer.render_related_terms(info)
        sections = """

{{-teny mifandraika-}}
* [[rt1]]"""
        self.assertEquals(synonyms, sections)

    def test_derived_terms(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.derived_terms = ['rt1']
        synonyms = renderer.render_related_terms(info)
        sections = """

{{-teny mifandraika-}}
* [[rt1]]"""
        self.assertEquals(synonyms, sections)

    def test_section(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.test_attribute = 'toskjf'
        section = renderer.render_section(info, '{{-test-header-}}', 'test_attribute')
        self.assertIn('{{-test-header-}}', section)

    def test_further_reading(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.further_reading = ''
        further_reading = renderer.render_further_reading(info)
        self.assertIn('{{-famakiana fanampiny-}}', further_reading)

    def test_references(self):
        renderer = MGWikiPageRenderer()
        info = MagicMock()
        info.references = ['']
        references = renderer.render_references(info)
        self.assertIn('{{-tsiahy-}}', references)

    def test_delete_section(self):
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
        self.assertEquals(removed_section, expected)

    def test_delete_section_other(self):
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
        self.assertEquals(removed_section, expected)
