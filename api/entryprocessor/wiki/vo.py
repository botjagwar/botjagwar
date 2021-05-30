# coding: utf8

import re
import pywikibot
from .base import WiktionaryProcessor
from .base import data_file


class VOWiktionaryProcessor(WiktionaryProcessor):
    @property
    def language(self):
        return 'vo'

    def get_WW_definition(self):
        return self._get_param_in_temp("Samafomot:VpVöd", 'WW')

    def _get_param_in_temp(self, templatestr, parameterstr):
        # print templatestr, parameterstr
        RET_text = ""
        templates_withparams = self.Page.templatesWithParams()
        for template in templates_withparams:
            if template[0].title() == templatestr:
                for params in template[1]:
                    if params.startswith(parameterstr + '='):
                        RET_text = params[len(parameterstr) + 1:]
        return RET_text

    def getall(self, keepNativeEntries=False):
        POStran = {"värb": 'mat',
                   'subsat': 'ana',
                   'ladyek': 'mpam-ana'}

        POS = self._get_param_in_temp('Samafomot:VpVöd', 'klad')
        definition = self.get_WW_definition()
        if POS in POStran:
            postran = POStran[POS]
        else:
            postran = POS

        return postran, 'vo', definition

    def retrieve_translations(self, page_c):
        pass