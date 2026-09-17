from unittest import TestCase

import mwparserfromhell

from api.parsers.etymology.en import render_template


class TestEtymologyTemplates(TestCase):
    def test_affix_template(self) -> None:
        template_expression = "{{af|es|a-|babilla|t2=the stifle (as of a horse)|-ar}}"
        tpl = mwparserfromhell.parse(template_expression).filter_templates()[0]
        result = render_template(tpl)
        self.assertEqual(
            result,
            "{{es}} a- + ''babilla'' (''the stifle (as of a horse)'') + -ar",
        )

    def test_prefix_template_with_positions_and_glosses(self) -> None:
        template_expression = "{{prefix|egy|s|pos1=causative prefix|rḫ|gloss2=to know, to learn}}"
        tpl = mwparserfromhell.parse(template_expression).filter_templates()[0]
        result = render_template(tpl)
        self.assertEqual(
            result,
            "s- (causative prefix) + rḫ (to know, to learn)",
        )

    def test_inherited_template(self) -> None:
        template_expression = "{{inh|mg|poz-pro|*habaRat||southwest monsoon}}"
        tpl = mwparserfromhell.parse(template_expression).filter_templates()[0]
        result = render_template(tpl)
        self.assertEqual(
            result,
            "{{poz-pro}} ''*habaRat'' (''southwest monsoon'')",
        )

    def test_cognate_template(self) -> None:
        template_expression = "{{cog|ms|barat||[[west]]}}"
        tpl = mwparserfromhell.parse(template_expression).filter_templates()[0]
        result = render_template(tpl)
        self.assertEqual(result, "{{ms}} ''barat'' (''west'')")

    def test_learned_borrowing_template(self) -> None:
        template_expression = "{{lbor|en|la|magister||teacher}}"
        tpl = mwparserfromhell.parse(template_expression).filter_templates()[0]
        result = render_template(tpl)
        self.assertEqual(
            result,
            "learned borrowing from {{la}} ''magister'' (''teacher'')",
        )

    def test_noncognate_template(self) -> None:
        template_expression = "{{ncog|fr|fromage||cheese}}"
        tpl = mwparserfromhell.parse(template_expression).filter_templates()[0]
        result = render_template(tpl)
        self.assertEqual(result, "not cognate with {{fr}} ''fromage'' (''cheese'')")

    def test_abbreviation_template(self) -> None:
        template_expression = "{{abbrev|en|personal computer}}"
        tpl = mwparserfromhell.parse(template_expression).filter_templates()[0]
        result = render_template(tpl)
        self.assertEqual(result, "Abbreviation of {{en}} ''personal computer''")

    def test_uncertain_template(self) -> None:
        template_expression = "{{uncertain}}"
        tpl = mwparserfromhell.parse(template_expression).filter_templates()[0]
        result = render_template(tpl)
        self.assertEqual(result, "Uncertain")

    def test_doublet_template(self) -> None:
        template_expression = "{{doublet|en|chief|chef}}"
        tpl = mwparserfromhell.parse(template_expression).filter_templates()[0]
        result = render_template(tpl)
        self.assertEqual(
            result,
            "Doublet of {{en}} ''chief'' and {{en}} ''chef''",
        )

    def test_root_template(self) -> None:
        template_expression = "{{root|en|ine-pro|*trewd-}}"
        tpl = mwparserfromhell.parse(template_expression).filter_templates()[0]
        self.assertEqual(render_template(tpl), "{{ine-pro}} ''*trewd-''")

    def test_legacy_etyl_template(self) -> None:
        template_expression = "{{etyl|enm|en}}"
        tpl = mwparserfromhell.parse(template_expression).filter_templates()[0]
        self.assertEqual(render_template(tpl), "{{enm}}")
