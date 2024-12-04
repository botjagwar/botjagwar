# coding: utf8


class Autoformat(object):
    """
    Autoformats any wikitext into something readable
    """

    def __init__(self, wikitext):
        self.text = wikitext
        self.summaries = ["[[Wiktionary:Firafitry_ny_teny_iditra|Firafitra]]"]

    # TODO
    def _replace_jereo_template(self):
        new_txt = self.text
        # ...
        begin_jereo = new_txt.find("{{jereo")
        end_jereo = new_txt.find("}}", begin_jereo)
        jereo_template = new_txt[begin_jereo : end_jereo + 2]

        print((begin_jereo, end_jereo))

        new_txt = new_txt.replace(jereo_template, "")
        new_txt = jereo_template + "\n" + new_txt

        if self.text != new_txt:
            self.summaries.append("mamerina ny endrika jereo")
            self.text = new_txt

    # TODO
    def _change_pronunciation_call(self):
        new_txt = self.text
        if new_txt.find("{{pron|"):
            new_txt = new_txt.replace("{{pron|", "{{fanononana|")
        if new_txt.find("{{pron X-SAMPA|"):
            new_txt = new_txt.replace("{{pron X-SAMPA|", "{{fanononana X-SAMPA|")
        if self.text != new_txt:
            self.summaries.append("manova ny fiantsoana ny endrika fanononana")
            self.text = new_txt

    # TODO
    def _remove_interwikis(self):
        new_txt = self.text
        # ...
        if self.text != new_txt:
            self.summaries.append("manala interwiki")
            self.text = new_txt

    # TODO
    def wikitext(self):
        self._change_pronunciation_call()
        self._remove_interwikis()
        self._replace_jereo_template()
        summary_sum = "; ".join(self.summaries)
        return self.text, summary_sum


def test():
    new_text = """
=={{=io=}}==
{{-ana-|io}}
'''be''' {{fanononana X-SAMPA||io}} {{fanononana||io}}
# [[renitantely]], [[renitantely]] {{dikantenin'ny dikanteny|bee|en}}
{{jereo|-be|-bé|be-|bè|bé|bê|bē|bə|bẹ|bẻ|bẽ|bế|bề|bể|bễ}}
=={{=tr=}}==
{{-ana-|tr}}
'''be''' {{fanononana X-SAMPA||tr}} {{fanononana||tr}}
# [[renitantely]], [[renitantely]]{{dikantenin'ny dikanteny|bee|en}}

=={{=pl=}}==
{{-ana-|pl}}
'''be''' {{fanononana X-SAMPA||pl}} {{fanononana||pl}}
# [[renitantely]], [[renitantely]]{{dikantenin'ny dikanteny|bee|en}}
"""
    result, _ = Autoformat(new_text).wikitext()
    print(result)


if __name__ == "__main__":
    test()
