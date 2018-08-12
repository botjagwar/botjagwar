import inspect
import sys
import warnings
from typing import Type

from object_model.word import Entry


class PageRenderer(object):
    def render(self, info: Entry) -> str:
        raise NotImplementedError()


class MGWikiPageRenderer(PageRenderer):
    def render(self, info: Entry, link=True) -> str:
        additional_note = ""
        data = info.to_dict()
        if 'origin_wiktionary_page_name' in data and 'origin_wiktionary_edition' in data:
            additional_note = " {{dikantenin'ny dikanteny|%(origin_wiktionary_page_name)s|%(origin_wiktionary_edition)s}}\n" % data

        s = """
        =={{=%(language)s=}}==
        {{-%(part_of_speech)s-|%(language)s}}
        '''{{subst:BASEPAGENAME}}''' {{fanononana X-SAMPA||%(language)s}} {{fanononana||%(language)s}}""" % data
        if link:
            s += "\n# %s" % ', '.join(['[[%s]]' % (d) for d in info.entry_definition])
        else:
            s += "\n# %s" % ', '.join(['%s' % (d) for d in info.entry_definition])

        s = s + additional_note % info.properties
        try:
            return s
        except UnicodeDecodeError:
            return s.decode('utf8')


class WikiPageRendererFactory(object):
    def __new__(cls, wiki) -> Type[PageRenderer]:
        assert type(wiki) == str
        ct_module = sys.modules[__name__]
        classes = inspect.getmembers(ct_module, inspect.isclass)
        processors = [x for x in classes if x[0].endswith('WikiPageRenderer')]
        language_class_name = "%sWikiPageRenderer" % wiki.upper()

        for current_class_name, processor_class in processors:
            if current_class_name == language_class_name:
                return processor_class

        warnings.warn("Tsy nahitana praosesera: '%s'" % language_class_name, Warning)
        return PageRenderer
