from object_model.word import Entry
from .base import PageRenderer


class FJWikiPageRenderer(PageRenderer):
    def render(self, info: Entry, link=True) -> str:
        data = info.to_dict()
        s = """
{{-%(language)s-}}
'''{{subst:BASEPAGENAME}}'''""" % data
        if link:
            s += "\n# %s" % ', '.join(['[[%s]]' % (d)
                                      for d in info.entry_definition])
        else:
            s += "\n# %s" % ', '.join(['%s' % (d)
                                      for d in info.entry_definition])
        additional_note = '\n{{bot-made entry|%s}}' % info.origin_wiktionary_page_name
        s = s + additional_note
        try:
            return s
        except UnicodeDecodeError:
            return s.decode('utf8')
