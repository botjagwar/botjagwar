# coding: utf8

from .base import WiktionaryProcessor


class VOWiktionaryProcessor(WiktionaryProcessor):
    @property
    def language(self):
        return "vo"

    def get_WW_definition(self):
        return self._get_param_in_temp("Samafomot:VpVöd", "WW")

    def _get_param_in_temp(self, templatestr, parameterstr):
        # print templatestr, parameterstr
        RET_text = ""
        templates_withparams = self.Page.templatesWithParams()
        for template in templates_withparams:
            if template[0].title() == templatestr:
                for params in template[1]:
                    if params.startswith(f"{parameterstr}="):
                        RET_text = params[len(parameterstr) + 1 :]
        return RET_text

    def get_all_entries(self, keep_native_entries=False, **kw):
        POStran = {"värb": "mat", "subsat": "ana", "ladyek": "mpam-ana"}

        POS = self._get_param_in_temp("Samafomot:VpVöd", "klad")
        definition = self.get_WW_definition()
        postran = POStran.get(POS, POS)
        return postran, "vo", definition

    def retrieve_translations(self, page_c):
        pass
