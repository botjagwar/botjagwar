from unittest.case import TestCase
from unittest.mock import MagicMock

from api.output import Output


class TestOutput(TestCase):
    def test_wikipage_one_page(self):
        entry1 = MagicMock(
            entry='test1',
            language='l1',
            part_of_speech='ana',
            definitions=[
                'def1-1'])
        expected = """
=={{=l1=}}==

{{-ana-|l1}}
'''{{subst:BASEPAGENAME}}''' 
# [[def1-1]]
"""
        output = Output()
        rendered = output.wikipage(entry1)
        self.assertEquals(rendered.strip(), expected.strip())

    def test_wikipage_many_pages(self):
        entry1 = MagicMock(
            entry='test1',
            language='l1',
            part_of_speech='ana',
            definitions=[
                'def1-1'])
        entry1_1 = MagicMock(
            entry='test1',
            language='l1',
            part_of_speech='mpam',
            definitions=[
                'def1-2'])
        entry2 = MagicMock(
            entry='test2',
            language='l2',
            part_of_speech='ana',
            definitions=[
                'def2-1', 'def2-2'])
        entry3 = MagicMock(
            entry='test3',
            language='l3',
            part_of_speech='ana',
            definitions=[
                'def3-1', 'def3-2', 'def3-3'])

        expected = """
=={{=l1=}}==

{{-mpam-|l1}}
'''{{subst:BASEPAGENAME}}''' 
# [[def1-2]]

{{-ana-|l1}}
'''{{subst:BASEPAGENAME}}''' 
# [[def1-1]]

=={{=l2=}}==

{{-ana-|l2}}
'''{{subst:BASEPAGENAME}}''' 
# [[def2-1]]
# [[def2-2]]
=={{=l3=}}==

{{-ana-|l3}}
'''{{subst:BASEPAGENAME}}''' 
# [[def3-1]]
# [[def3-2]]
# [[def3-3]]
"""

        output = Output()
        rendered = output.wikipages([entry1, entry1_1, entry2, entry3])
        print(rendered)
        self.assertEquals(rendered.strip(), expected.strip())
