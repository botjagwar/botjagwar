import inspect
import sys
import warnings
from typing import Type

from .base import PageRenderer
from .chr import CHRWikiPageRenderer
from .fa import FAWikiPageRenderer
from .fj import FJWikiPageRenderer
from .mg import MGWikiPageRenderer


class WikiPageRendererFactory(object):
    def __new__(cls, wiki) -> Type[PageRenderer]:
        assert isinstance(wiki, str)
        ct_module = sys.modules[__name__]
        classes = inspect.getmembers(ct_module, inspect.isclass)
        processors = [x for x in classes if x[0].endswith("WikiPageRenderer")]
        language_class_name = f"{wiki.upper()}WikiPageRenderer"

        for current_class_name, processor_class in processors:
            if current_class_name == language_class_name:
                return processor_class

        warnings.warn(
            f"Failed to find page renderer for: '{language_class_name}'", Warning
        )
        return PageRenderer
