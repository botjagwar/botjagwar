from api.model.word import Entry
from .base import PageRenderer


class FAWikiPageRenderer(PageRenderer):
    def render(self, info: Entry, link=True) -> str:
        data = info.serialise()
        s = (
            """
{{-%(language)s-}}
'''{{subst:BASEPAGENAME}}'''"""
            % data
        )
        if link:
            s += "\n# %s" % ", ".join([f"[[{d}]]" for d in info.definitions])
        else:
            s += "\n# %s" % ", ".join([f"{d}" for d in info.definitions])
        additional_note = (
            "\n{{bot-made translation|%s}}" % info.origin_wiktionary_page_name
        )
        s = s + additional_note
        try:
            return s
        except UnicodeDecodeError:
            return s.decode("utf8")
