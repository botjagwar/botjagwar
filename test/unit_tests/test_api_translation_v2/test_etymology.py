"""Tests for deterministic English-to-Malagasy etymology translation."""

from __future__ import annotations

import pytest

from api.translation_v2.functions.etymology import (
    translate_etymologies,
    translate_etymology,
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "From {{inh|en|enm|þristen|þrusten}}.",
            "Avy amin'ny {{enm}} ''þrusten''.",
        ),
        (
            "From {{der|da|non|hǫrr}}.",
            "Avy amin'ny {{non}} ''hǫrr''.",
        ),
        (
            "Borrowed from {{bor|de|en|bug}}.",
            "Nindramina avy amin'ny {{en}} ''bug''.",
        ),
        (
            "{{bor+|ru|fr|paysan||peasant}}.",
            "Nindramina avy amin'ny {{fr}} ''paysan'' (midika hoe ''peasant'').",
        ),
        (
            "{{lbor|en|la|magister||teacher}}",
            "Nindramina ara-pahaizana avy amin'ny {{la}} ''magister'' "
            "(midika hoe ''teacher'').",
        ),
        (
            "{{cal|en|fr|gratte-ciel}}.",
            "Dikanteny ara-bakiteny avy amin'ny {{fr}} ''gratte-ciel''.",
        ),
        (
            "{{psm|zh|en|toffee}}.",
            "Fampitoviana feo sy hevitra amin'ny {{en}} ''toffee''.",
        ),
        (
            "From {{inh|ca|pro|fin}}, from {{inh|ca|la|fīnis}}.",
            "Avy amin'ny {{pro}} ''fin'', avy amin'ny {{la}} ''fīnis''.",
        ),
        (
            "Probably via {{der|yi|de|Bank}} from {{der|yi|it|banco}}.",
            "Azo inoana fa nandalo tamin'ny {{de}} ''Bank'' avy amin'ny "
            "{{it}} ''banco''.",
        ),
        (
            "Via [[Gallo-Romance]] from {{der|ca|frk|*būkō}}.",
            "Nandalo tamin'ny [[Gallo-Romance]] avy amin'ny {{frk}} ''*būkō''.",
        ),
        (
            "From {{etyl|grc|el}} {{m|grc|ὅρος}}.",
            "Avy amin'ny {{grc}} ''ὅρος''.",
        ),
        (
            "From {{bor|pl|la|versus}}. Cognates include {{cog|uk|вірш}}, "
            "{{cog|be|верш}}.",
            "Avy amin'ny {{la}} ''versus''. Anisan'ny teny mitovy fiaviana aminy "
            "ny {{uk}} ''вірш'', {{be}} ''верш''.",
        ),
        (
            "Compare {{cog|th|พอง||to swell; swollen}}.",
            "Ampitahao amin'ny {{th}} ''พอง'' (midika hoe ''to swell; swollen'').",
        ),
        (
            "Compare {{cog|akl|ani}}, {{cog|ceb|ani}}, and {{cog|tsg|ani}}.",
            "Ampitahao amin'ny {{akl}} ''ani'', {{ceb}} ''ani'', sy "
            "{{tsg}} ''ani''.",
        ),
        (
            "From {{inh|en|enm|gapynge}}; equivalent to "
            "{{suffix|en|gape|ing}}.",
            "Avy amin'ny {{enm}} ''gapynge''; mitovy amin'ny ''gape'' + -ing.",
        ),
        (
            "Related to {{m|it|acciughero}}.",
            "Mifandray amin'ny {{it}} ''acciughero''.",
        ),
        (
            "See [[høre#Danish|høre]].",
            "Jereo [[høre#Danish|høre]].",
        ),
        (
            "Inflected form of {{m|lb|huelen}}.",
            "Endrika miovaovan'ny {{lb}} ''huelen''.",
        ),
        (
            "A variant of {{m|en|wrout}}.",
            "Endrika hafa amin'ny {{en}} ''wrout''.",
        ),
        (
            "Short form of {{m|pl|rzut karny}}.",
            "Endrika nohafohezina amin'ny {{pl}} ''rzut karny''.",
        ),
        (
            "Back-formation from {{m|en|yorker}}.",
            "Avy amin'ny fanesorana ampahany amin'ny {{en}} ''yorker''.",
        ),
        (
            "Deverbal noun from {{m|ru|припасти́}}.",
            "Anarana avy amin'ny matoanteny {{ru}} ''припасти́''.",
        ),
        (
            "Cognate to {{cog|fr|fromage}}.",
            "Mitovy fiaviana amin'ny {{fr}} ''fromage''.",
        ),
        (
            "From the verb {{m|nl|uitgeven}}.",
            "Avy amin'ny matoanteny {{nl}} ''uitgeven''.",
        ),
        (
            "Diminutive of {{m|es|casa}}.",
            "Endrika fanalefahana ny {{es}} ''casa''.",
        ),
        (
            "Shortened from {{m|en|telephone}}.",
            "Nohafohezina avy amin'ny {{en}} ''telephone''.",
        ),
        (
            "From {{inh|mt|ar|qiyas}} and/or {{m|ar|qays}}.",
            "Avy amin'ny {{ar}} ''qiyas'' sy/na {{ar}} ''qays''.",
        ),
        (
            "Cognate to or borrowed from {{bor|tig|ar|sur}}.",
            "Mitovy fiaviana amin'ny na nindramina avy amin'ny {{ar}} ''sur''.",
        ),
        (
            "From {{inh|pt|roa-opt|quintal}}; or from "
            "{{suffix|pt|quinta|al}}.",
            "Avy amin'ny {{roa-opt}} ''quintal''; na avy amin'ny "
            "''quinta'' + -al.",
        ),
        (
            "Possibly from {{m|es|fraise}}, or from the verb {{m|es|fresar}}.",
            "Mety avy amin'ny {{es}} ''fraise'', na avy amin'ny matoanteny "
            "{{es}} ''fresar''.",
        ),
        (
            "From {{der|es|VL.|cottus}}.",
            "Avy amin'ny {{VL.}} ''cottus''.",
        ),
        (
            "Borrowed from {{bor|cy|enm|term}}, from {{der|cy|ONF.|cote}}.",
            "Nindramina avy amin'ny {{enm}} ''term'', avy amin'ny "
            "{{ONF.}} ''cote''.",
        ),
        (
            "From {{der|pt|it|grana||cash < grain}}, from "
            "{{der|pt|la|granum||raw > hard}}.",
            "Avy amin'ny {{it}} ''grana'' (midika hoe ''cash < grain''), "
            "avy amin'ny {{la}} ''granum'' (midika hoe ''raw > hard'').",
        ),
        (
            "Possibly from {{m|en|source}} or related to {{m|en|other}}.",
            "Mety avy amin'ny {{en}} ''source'' na mifandray amin'ny "
            "{{en}} ''other''.",
        ),
        (
            "Imitative, or variant of {{m|en|knell}}.",
            "Avy amin'ny fanahafana feo, na endrika hafa amin'ny "
            "{{en}} ''knell''.",
        ),
        (
            "From a variant of {{m|en|burst}}.",
            "Avy amin'ny endrika hafa amin'ny {{en}} ''burst''.",
        ),
        (
            "From or related to {{m|rup|fluiara}}.",
            "Avy amin'ny na mifandray amin'ny {{rup}} ''fluiara''.",
        ),
        (
            "From {{suffix|en|squall|y}}; from 1719.",
            "Avy amin'ny ''squall'' + -y; avy amin'ny 1719.",
        ),
        (
            "See more at {{m|en|light}}.",
            "Jereo koa {{en}} ''light''.",
        ),
        (
            "From {{cog|Lunfardo|-}}, possibly from {{der|es|fr|croupier}}.",
            "Avy amin'ny {{es-lun}}, mety avy amin'ny {{fr}} ''croupier''.",
        ),
        (
            "Cognates include {{cog|kpv|tr=laped}} and {{cog|mns|tr=lep}}.",
            "Anisan'ny teny mitovy fiaviana aminy ny {{kpv}} "
            "(soratana hoe ''laped'') sy {{mns}} (soratana hoe ''lep'').",
        ),
        (
            "From clipping of {{bor|th|en|lingerie}}.",
            "Avy amin'ny endrika nohafohezina avy amin'ny {{en}} ''lingerie''.",
        ),
        (
            "From inflected form of {{m|pt|perder}}.",
            "Avy amin'ny endrika miovaovan'ny {{pt}} ''perder''.",
        ),
        (
            "Perhaps from or related to {{der|ga|mga|apach}}.",
            "Mety avy amin'ny na mifandray amin'ny {{mga}} ''apach''.",
        ),
        (
            "Cognate with {{cog|inc-hnd}} {{m|ur|ghatna}}.",
            "Mitovy fiaviana amin'ny {{inc-hnd}} {{ur}} ''ghatna''.",
        ),
        (
            "From or cognate to {{der|yi|de|Schmiere}}.",
            "Avy amin'ny na mitovy fiaviana amin'ny {{de}} ''Schmiere''.",
        ),
        (
            "From {{m|en|source}}; or from or cognate with "
            "{{der|en|non|othlask}}.",
            "Avy amin'ny {{en}} ''source''; na avy amin'ny na mitovy "
            "fiaviana amin'ny {{non}} ''othlask''.",
        ),
    ],
    ids=[
        "inheritance",
        "derivation",
        "borrowing",
        "standalone-borrowing",
        "learned-borrowing",
        "calque",
        "phono-semantic-match",
        "origin-chain",
        "probable-via-chain",
        "via-link",
        "legacy-language-template",
        "cognate-sentence",
        "comparison",
        "serial-comparison",
        "equivalent-morphology",
        "related-term",
        "cross-reference",
        "inflected-form",
        "variant",
        "short-form",
        "back-formation",
        "deverbal-noun",
        "cognate-to",
        "from-verb",
        "diminutive",
        "shortened-from",
        "and-or",
        "cognate-or-borrowed",
        "semicolon-or-from",
        "or-from-verb",
        "dotted-language-code",
        "legacy-dotted-language-code",
        "comparison-symbols-in-glosses",
        "or-related-to",
        "imitative-or-variant",
        "from-variant",
        "from-or-related",
        "numeric-origin",
        "see-more-at",
        "language-name-alias",
        "transliterated-termless-cognates",
        "from-clipping",
        "from-inflected-form",
        "perhaps-from-or-related",
        "language-group-cognate",
        "from-or-cognate",
        "or-from-or-cognate",
    ],
)
def test_translates_corpus_derived_connective_rules(source: str, expected: str) -> None:
    """Translate common complete grammar patterns found in the corpus."""

    assert translate_etymology(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "{{ar-elative|nocap=1}} of "
            "{{m|ar|حَمِيد||[[praiseworthy]]; [[benign]]}}, "
            "from the root {{ar-root|ح م د}}",
            "Endrika fampitahana amin'ny {{ar}} ''حَمِيد'' "
            "(midika hoe ''praiseworthy; benign''), avy amin'ny fototeny "
            "{{ar}} ''ح م د''.",
        ),
        (
            "{{ar-active participle|nocap=1}} of "
            "{{m|ar|جَدَّ||to be [[serious]]}}, "
            "from the root {{ar-root|ج د د}}.",
            "Ova-matoanteny enti-manao avy amin'ny {{ar}} ''جَدَّ'' "
            "(midika hoe ''to be serious''), avy amin'ny fototeny "
            "{{ar}} ''ج د د''.",
        ),
        (
            "{{ar-active participle|lc=1|noderived=1|nocat=1}} of the verb "
            "{{m|ar|بَلَغَ||to [[reach]]}}, from the root "
            "{{ar-root|ب ل غ}}?",
            "Ova-matoanteny enti-manao avy amin'ny {{ar}} ''بَلَغَ'' "
            "(midika hoe ''to reach''), avy amin'ny fototeny "
            "{{ar}} ''ب ل غ''?",
        ),
        (
            "{{ar-active participle|arz}} of {{m|arz|base}}, from the root "
            "{{ar-root|r o o t}}.",
            "Ova-matoanteny enti-manao avy amin'ny {{arz}} ''base'', "
            "avy amin'ny fototeny {{ar}} ''r o o t''.",
        ),
        (
            "From {{m|en|ordinary}}. {{ar-elative}} of {{m|ar|base}}, "
            "from the root {{ar-root|r o o t}}.",
            "Avy amin'ny {{en}} ''ordinary''. Endrika fampitahana amin'ny "
            "{{ar}} ''base'', avy amin'ny fototeny {{ar}} ''r o o t''.",
        ),
    ],
    ids=[
        "elative",
        "active-participle",
        "active-participle-verb",
        "active-participle-lect",
        "neighboring-statement",
    ],
)
def test_translates_typed_form_derivation_clauses(
    source: str, expected: str
) -> None:
    """Parse form, base, and root roles before controlled rendering."""

    assert translate_etymology(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "{{ar-elative}} of the verb {{m|ar|حَمِيد}}, from the root "
        "{{ar-root|ح م د}}.",
        "{{ar-elative}} of {{unknown}}, from the root {{ar-root|ح م د}}.",
        "{{ar-elative}} of {{m|ar|حَمِيد}}, from the root {{m|ar|ح م د}}.",
        "{{ar-elative}} of {{m|ar|حَمِيد}} from the root {{ar-root|ح م د}}.",
        "{{ar-elative}} of {{m|ar|حَمِيد}}, from the root "
        "{{ar-root|ح م د}} with unexplained prose.",
        "{{ar-elative|unsupported=1}} of {{m|ar|حَمِيد}}, from the root "
        "{{ar-root|ح م د}}.",
        "{{ar-elative|noderived=1}} of {{m|ar|حَمِيد}}, from the root "
        "{{ar-root|ح م د}}.",
        "{{ar-active participle|notext=1}} of {{m|ar|base}}, from the root "
        "{{ar-root|r o o t}}.",
        "{{ar-elative}} of {{bor|ar|fr|base}}, from the root "
        "{{ar-root|r o o t}}.",
        "{{ar-elative}} of {{m|en|base}}, from the root "
        "{{ar-root|r o o t}}.",
        "{{ar-elative}} of {{m|ar|base}}, from the root "
        "{{he-root|r|o|t}}.",
        "{{ar-active participle|fr}} of {{m|fr|base}}, from the root "
        "{{ar-root|r o o t}}.",
        "{{ar-active participle|bbz}} of {{m|bbz|base}}, from the root "
        "{{ar-root|r o o t}}.",
    ],
    ids=[
        "invalid-verb-modifier",
        "nonlexical-base",
        "term-in-root-position",
        "missing-relation-comma",
        "trailing-prose",
        "unsupported-form-parameter",
        "elative-active-only-parameter",
        "unsupported-display-parameter",
        "relation-bearing-base",
        "mismatched-base-language",
        "non-arabic-root",
        "non-arabic-lect",
        "invalid-upstream-arabic-code",
    ],
)
def test_typed_form_derivation_clauses_fail_closed(source: str) -> None:
    """Reject incomplete, ambiguous, or partially consumed form clauses."""

    assert translate_etymology(source) is None


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "{{suffix|en|Bermuda|an}}",
            "Avy amin'ny fampiarahana ny ''Bermuda'' + -an.",
        ),
        (
            "{{prefix|en|re|man}}",
            "Avy amin'ny fampiarahana ny re- + ''man''.",
        ),
        (
            "From {{prefix|ha|ba|}} {{der|ha|ar|arab}}.",
            "Avy amin'ny ba- {{ar}} ''arab''.",
        ),
        (
            "From {{bor|en|grc|pedon}} + {{af|en|-ality}}.",
            "Avy amin'ny {{grc}} ''pedon'' + -ality.",
        ),
        (
            "{{compound|nl|over|rijden}}",
            "Teny mitambatra avy amin'ny ''over'' + ''rijden''.",
        ),
        (
            "{{com|fi|geeni|teknologia}}",
            "Teny mitambatra avy amin'ny ''geeni'' + ''teknologia''.",
        ),
        (
            "{{blend|en|point|voxel}}",
            "Teny mifangaro avy amin'ny ''point'' + ''voxel''.",
        ),
        (
            "{{blend|ja|bloomers|sailor suit|}}",
            "Teny mifangaro avy amin'ny ''bloomers'' + ''sailor suit''.",
        ),
        (
            "{{compound|cy|cyntaf|-in|}}",
            "Teny mitambatra avy amin'ny ''cyntaf'' + -in.",
        ),
        (
            "{{af|ga|spáráil|t1=husband, conserve|pos1=v|-aí|"
            "pos2=agent suffix}}",
            "Avy amin'ny fampiarahana ny ''spáráil'' "
            "(midika hoe ''husband, conserve'') (sokajy: ''v'') + -aí "
            "(sokajy: ''agent suffix'').",
        ),
        (
            "{{af|lv|word|t1=to rest <small>(past stem)</small>|-a|"
            "t2=ending}}",
            "Avy amin'ny fampiarahana ny ''word'' "
            "(midika hoe ''to rest (past stem)'') + -a "
            "(midika hoe ''ending'').",
        ),
        (
            "{{root|en|ine-pro|*trewd-}}",
            "Avy amin'ny fototeny {{ine-pro}} ''*trewd-''.",
        ),
        (
            "From the root {{ar-root|ر|م|ح}}.",
            "Avy amin'ny fototeny {{ar}} ''ر م ح''.",
        ),
        (
            "{{ar-root|ح|ض|ر|notext=1}}",
            "{{ar}} ''ح ض ر''.",
        ),
        (
            "{{abbreviation of|en|personal computer}}",
            "Fanafohezana ny {{en}} ''personal computer''.",
        ),
        (
            "{{clipping|en|celibate}}.",
            "Endrika nohafohezina avy amin'ny {{en}} ''celibate''.",
        ),
        (
            "{{deverbal|es|reintegrar|t=to reintegrate}}.",
            "Avy amin'ny matoanteny {{es}} ''reintegrar'' "
            "(midika hoe ''to reintegrate'').",
        ),
        (
            "{{doublet|en|chief|chef}}.",
            "Teny iray fiaviana amin'ny {{en}} ''chief'' sy {{en}} ''chef''.",
        ),
        ("{{unknown}}", "Tsy fantatra ny fiaviany."),
        ("{{uncertain}}.", "Tsy azo antoka ny fiaviany."),
        ("{{onomatopoeic|de}}", "Avy amin'ny fanahafana feo."),
        ("Unknown.", "Tsy fantatra ny fiaviany."),
        ("Imitative.", "Avy amin'ny fanahafana feo."),
    ],
    ids=[
        "suffix",
        "prefix",
        "prefix-with-omitted-base",
        "externally-bound-single-affix",
        "compound",
        "compound-alias",
        "blend",
        "blend-trailing-placeholder",
        "compound-trailing-placeholder",
        "annotated-affix",
        "formatted-affix-annotation",
        "root",
        "arabic-root",
        "suppressed-root-text",
        "abbreviation-template-alias",
        "clipping",
        "deverbal-template",
        "doublet",
        "unknown-template",
        "uncertain-template",
        "onomatopoeia-template",
        "unknown-text",
        "imitative-text",
    ],
)
def test_translates_standalone_rule_templates(source: str, expected: str) -> None:
    """Give relation-bearing templates explicit Malagasy surface text."""

    assert translate_etymology(source) == expected


def test_preserves_all_supported_term_metadata() -> None:
    """Keep lexical metadata opaque while translating its structural labels."""

    source = (
        "From {{m|und|term|tr=roman|ts=spoken|t=meaning|lit=literal|"
        "pos=noun|g=f|q=dialectal|id=sense|sc=Latn|sort=term}}."
    )

    assert translate_etymology(source) == (
        "Avy amin'ny {{und}} ''term'' (soratana hoe ''roman'') "
        "(tononina hoe ''spoken'') (midika hoe ''meaning'') "
        "(ara-bakiteny hoe ''literal'') (sokajy: ''noun'') "
        "(fitsipi-pitenenana: ''f'') (fanamarihana: ''dialectal'')."
    )


def test_preserves_multiple_qualifier_and_gender_parameters() -> None:
    """Retain every accepted semantic alias rather than only the first one."""

    source = "From {{m|und|term|g=s|g2=p|q=dialectal|qq=rare}}."

    assert translate_etymology(source) == (
        "Avy amin'ny {{und}} ''term'' (fitsipi-pitenenana: ''s, p'') "
        "(fanamarihana: ''dialectal, rare'')."
    )

def test_preserves_named_transliteration_and_gloss() -> None:
    """Keep explicit transliteration and gloss fields distinct."""

    source = "{{inh+|as|sa|śālā|শালা|tr=śālā|t=shed, stable, house}}"

    assert translate_etymology(source) == (
        "Nolovaina avy amin'ny {{sa}} ''শালা'' (soratana hoe ''śālā'') "
        "(midika hoe ''shed, stable, house'')."
    )


def test_preserves_component_metadata() -> None:
    """Retain per-component language, transliteration, and literal meaning."""

    source = "{{compound|ja|空|文|lang1=zh|tr1=kōng|lit2=writing|q2=rare}}"

    assert translate_etymology(source) == (
        "Teny mitambatra avy amin'ny {{zh}} ''空'' (soratana hoe ''kōng'') + "
        "''文'' (ara-bakiteny hoe ''writing'') (fanamarihana: ''rare'')."
    )


def test_uses_html_italics_when_apostrophes_would_break_wikitext() -> None:
    """Avoid creating ambiguous runs of wiki apostrophes around terms."""

    assert translate_etymology("From {{m|und|gndk'|tr=gndk'}}.") == (
        "Avy amin'ny {{und}} <i>gndk'</i> (soratana hoe <i>gndk'</i>)."
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "{{wikipedia}} From {{inh|mg|poz-pro|*qelad}}.<ref>source</ref>",
            "Avy amin'ny {{poz-pro}} ''*qelad''.",
        ),
        (
            "From {{inh|mg|poz-pro|*qelad}}<!-- editor note -->.",
            "Avy amin'ny {{poz-pro}} ''*qelad''.",
        ),
        ("From [[Germanic]].", "Avy amin'ny [[Germanic]]."),
        ("From <i>fug-</i>.", "Avy amin'ny <i>fug-</i>."),
        ("From ''*rena''.", "Avy amin'ny ''*rena''."),
        ("See [[source|''label'']].", "Jereo [[source|''label'']]."),
        ("From ''{{l|fr|peloton}}''.", "Avy amin'ny {{fr}} ''peloton''."),
        ("From '''[[Brassica]]'''.", "Avy amin'ny '''[[Brassica]]'''."),
        (
            "{{inh+|hi|psu|dehali}}, from {{inh|hi|sa|dehali|t=terrace}}.",
            "Nolovaina avy amin'ny {{psu}} ''dehali'', avy amin'ny {{sa}} "
            "''dehali'' (midika hoe ''terrace'').",
        ),
        (
            "From {{bor|fr|it|giargone}}. {{doublet|fr|zircon}}.",
            "Avy amin'ny {{it}} ''giargone''. Teny iray fiaviana amin'ny "
            "{{fr}} ''zircon''.",
        ),
        (
            "From {{m|en|a}}.{{bor+|und|fr|b}}.",
            "Avy amin'ny {{en}} ''a''. Nindramina avy amin'ny {{fr}} ''b''.",
        ),
        (
            "From {{m|en|a}}.Borrowed from {{m|fr|b}}.",
            "Avy amin'ny {{en}} ''a''. Nindramina avy amin'ny {{fr}} ''b''.",
        ),
    ],
    ids=[
        "ignored-metadata-and-reference",
        "comment",
        "wikilink",
        "html-italics",
        "italic-protoform",
        "formatted-link-label",
        "wrapped-link-template",
        "bold-lexical-link",
        "leading-standalone-relation",
        "sentence-boundary-relation",
        "unspaced-sentence-boundary",
        "unspaced-text-sentence-boundary",
    ],
)
def test_preserves_safe_markup_and_relation_boundaries(
    source: str, expected: str
) -> None:
    """Preserve lexical markup without dropping a template's relation."""

    assert translate_etymology(source) == expected


def test_renders_late_middle_chinese_link_template() -> None:
    """Render the corpus's frequent fixed-language link template losslessly."""

    assert translate_etymology(
        "From {{bor|km|ltc|-}} {{ltc-l|膠|glue|id=1}}."
    ) == "Avy amin'ny {{ltc}} ''膠'' (midika hoe ''glue'')."


@pytest.mark.parametrize(
    "source",
    [
        "",
        " ",
        "From an undocumented source.",
        "From.",
        "and.",
        "Unknown123.",
        "From from {{m|en|source}}.",
        "From {{m|en|a}} and.",
        "From {{m|en|a}}; from.",
        "From {{unsupported-origin|en|source}}.",
        "From {{m|PAGENAME|term}}.",
        "From {{m|delete|term}}.",
        "From {{m|en|__NOTOC__}}.",
        "From {{m|en|&#123;&#123;PAGENAME&#125;&#125;}}.",
        "From {{m|en|&#95;&#95;NOTOC&#95;&#95;}}.",
        "From {{m|en|__NO<!--x-->TOC__}}.",
        "From {{m|en|__NO<small></small>TOC__}}.",
        "From <i>__NOTOC__</i>.",
        "From <i>{{unsupported|payload}}</i>.",
        "From [[target|{{unsupported|payload}}]].",
        "From <i>[[Category:Injected]]</i>.",
        "From [[target|[[File:Example.jpg]]]].",
        "From {{m|en|[[File:Example.jpg|25px]]}}.",
        "From {{m|en|term|tr=[[Image:Example.jpg|30px]]}}.",
        "From <b>source</b>.",
        "{{nonlemma}}",
        "{{rfe|en}}",
        "====Noun====\n{{en-noun}}",
        "* {{sense|booklet}}, from {{m|de|Heft}}.",
        "[[File:example.jpg|thumb|caption]]",
        "From {{m|en|source}} and unexplained prose.",
        "From {{m|en|source|foo=lost meaning}}.",
        "From {{m|en|source|Q=rare}}.",
        "From {{m|en|term|t=first|gloss=second}}.",
        "From {{m|tr|term|tr={{m|tr|boza}}}}.",
        "{{af|pt|avião<t:plane>|-z-|-ão<pos:augmentative suffix>}}",
        "{{af|en|foo|bar<suffix>}}",
        "{{af|en|foo|bar<small:lost>}}",
        "{{af|en|foo|bar|t2=<small>unclosed}}",
        "From {{m|en|source|extra|gloss|unexpected}}.",
        "From {{inh|en|la|term|alternate|positional gloss|t=named gloss}}.",
        "From {{inh+|as|sa|term|alternate|positional|t=named}}.",
        "Compare {{cog|ca,oc,pt,es|salar}}.",
        "From {{m|en|source|" + "9" * 5_000 + "=value}}.",
        "From {{m|en|source|0=value}}.",
        "From {{m|en|source|01=value}}.",
        "{{suffix|en|source|ing|pos3=orphan annotation}}",
        "{{compound|en|foo|bar|t1=first|gloss1=second}}",
        "{{compound|en|foo|4=bar|t2=wrong-target}}",
        "{{compound|en|foo||bar|t2=lost}}",
        "{{compound|en|onlyone}}",
        "{{compound|bad code!|foo|bar}}",
        "{{bor|bad code!|en|term}}",
        "{{bor||en|term}}",
        "{{bor|en||term}}",
        "{{root|en||term}}",
        "From {{etyl|la|bad code!}} {{m|la|term}}.",
        "From {{etyl|la}} {{m|la|term}}.",
        "From {{m|0|term}}.",
        "From {{m|bad..code|term}}.",
        "From {{m|bad.|term}}.",
        "{{ltc-l|term|second|third}}",
        "{{onomatopoeic|ar|title=baby talk}}",
        "{{unk|it|title=Debated}}.",
        "{{m|en|source}}.",
        "From {{m|en}}.",
        "From <i></i>.",
        "From <i>&nbsp;</i>.",
        "{{af|en|onlyone}}",
        "{{prefix|en|onlyone}}",
        "{{suffix|en|onlyone}}",
        "From {{af|en|onlyone}}.",
        "Compare {{prefix|en|onlyone}}.",
        "{{af|en|onlyone|}}",
        "{{prefix|en|onlyone|}}",
        "{{cog|en}}",
        "[[source]].",
        "From {{m|en|source}},",
        "From {{m|en|source}},.<ref>source</ref>",
        "From {{m|en|source}}.<ref>source</ref> ; compare {{m|en|other}}.",
        "From {{m|en|a}}.borrowed from {{m|fr|b}}.",
        "From<!--x-->{{m|en|x}}.",
        "From {{m|en|a}}.<!--x-->borrowed from {{m|fr|b}}.",
        "From {{m|en|source}}..",
        "From ({{m|en|source}}.",
        "From{{m|en|source}}.",
        "From {{etyl|la|en}}{{m|la|term}}.",
        "From and {{m|en|source}}.",
        "From Unknown {{m|en|source}}.",
        "From {{cog|en}}, from {{m|fr|x}}.",
        "From {{etyl|la|en}}, from {{m|fr|x}}.",
        "From {{af|en|onlyone}} and {{m|fr|x}}.",
        "From {{cog|en}} {{m|fr|x}} {{cog|de}}.",
        "From {{m|fr|x}} {{cog|en}}.",
        "From , {{m|en|x}}.",
        ", From {{m|en|x}}.",
        "From &#44; {{m|en|x}}.",
        "From <i>,</i> {{m|en|x}}.",
        "From {{prefix|en|re|}} <i>,</i>.",
        "From {{prefix|en|re|}} [[target|\u200b]].",
        "From {{prefix|en|re|}} {{unknown}}.",
        "1From {{m|en|source}}.",
        "From {{m|en|a}}and {{m|en|b}}.",
        "{{unknown}} Related to {{m|en|source}}.",
        "From <small>source</small>.",
        "From {{m|en|source}.",
        "From \ue0000\ue001.",
    ],
    ids=[
        "empty",
        "whitespace",
        "free-prose",
        "incomplete-origin",
        "bare-connector",
        "missing-word-boundary",
        "consecutive-governors",
        "dangling-connector",
        "dangling-second-governor",
        "unknown-template",
        "magic-word-language-code",
        "untrusted-language-code",
        "behavior-switch-term",
        "entity-template-injection",
        "entity-behavior-switch",
        "comment-obfuscated-switch",
        "formatting-obfuscated-switch",
        "italic-behavior-switch",
        "nested-template-in-italics",
        "nested-template-in-link",
        "category-in-italics",
        "file-in-link-label",
        "file-in-template-term",
        "image-in-template-transliteration",
        "bold-opaque-prose",
        "nonlemma",
        "etymology-request",
        "leaked-heading",
        "list",
        "media",
        "partial-prose",
        "unknown-named-parameter",
        "uppercase-parameter",
        "conflicting-named-gloss",
        "nested-semantic-template",
        "inline-modifier",
        "colonless-inline-modifier",
        "formatting-prefix-bypass",
        "unclosed-formatting-tag",
        "extra-positional-parameter",
        "ambiguous-positional-gloss",
        "ambiguous-plus-positional-gloss",
        "multi-language-code",
        "oversized-parameter-index",
        "zero-parameter-index",
        "leading-zero-parameter-index",
        "orphan-component-annotation",
        "conflicting-component-gloss",
        "sparse-components",
        "explicit-empty-component",
        "one-part-compound",
        "invalid-morphology-language",
        "invalid-destination-language",
        "missing-destination-language",
        "missing-source-language",
        "missing-root-language",
        "invalid-etyl-destination",
        "missing-etyl-destination",
        "numeric-language-code",
        "double-dot-language-code",
        "trailing-dot-language-code",
        "conflicting-ltc-positional-gloss",
        "semantic-static-title",
        "unmapped-uncertainty",
        "bare-mention",
        "mention-without-term",
        "empty-italic-term",
        "visually-empty-italic-term",
        "one-part-affix",
        "one-part-prefix",
        "one-part-suffix",
        "from-one-part-affix",
        "compare-one-part-prefix",
        "trailing-empty-affix",
        "trailing-empty-prefix",
        "termless-cognate",
        "bare-link",
        "dangling-comma",
        "invalid-internal-punctuation",
        "invalid-recombined-punctuation",
        "unspaced-lowercase-sentence-boundary",
        "comment-manufactured-operand-space",
        "comment-manufactured-sentence-space",
        "double-period",
        "unbalanced-parenthesis",
        "missing-rule-operand-space",
        "adjacent-atoms",
        "connector-before-operand",
        "static-rule-before-operand",
        "unrelated-cognate-companion",
        "unrelated-language-companion",
        "unrelated-affix-companion",
        "shared-cognate-companion",
        "reversed-cognate-companion",
        "punctuation-before-governed-operand",
        "leading-punctuation",
        "entity-punctuation-before-operand",
        "italic-punctuation-before-operand",
        "punctuation-companion",
        "invisible-link-companion",
        "static-template-companion",
        "missing-leading-boundary",
        "missing-connector-spacing",
        "ambiguous-template-join",
        "unsupported-tag",
        "malformed-template",
        "reserved-marker",
    ],
)
def test_fails_closed_for_unsupported_or_ambiguous_input(source: str) -> None:
    """Never publish a partial rule translation as canonical etymology."""

    assert translate_etymology(source) is None


def test_rejects_oversized_input_before_parsing() -> None:
    """Bound deterministic work for untrusted source sections."""

    assert translate_etymology("Unknown." + " " * 10_001) is None


def test_rejects_unsupported_language_pairs() -> None:
    """Expose only the language pair whose rules are implemented."""

    assert translate_etymology("Unknown.", source="fr", target="mg") is None
    assert translate_etymology("Unknown.", source="en", target="fr") is None


def test_translates_a_batch_atomically_without_mutating_it() -> None:
    """Preserve section order and leave caller-owned source data unchanged."""

    sections = [
        "From {{inh|mg|poz-pro|*qelad}}.",
        "{{suffix|en|Bermuda|an}}",
    ]
    original = list(sections)

    assert translate_etymologies(sections) == [
        "Avy amin'ny {{poz-pro}} ''*qelad''.",
        "Avy amin'ny fampiarahana ny ''Bermuda'' + -an.",
    ]
    assert sections == original


@pytest.mark.parametrize(
    "sections",
    [
        [],
        "Unknown.",
        ["Unknown.", "unsupported prose"],
        ["Unknown.", None],
    ],
    ids=["empty", "string-is-not-batch", "one-unsupported", "non-string-item"],
)
def test_batch_fails_closed(sections: object) -> None:
    """Suppress the whole canonical batch when any section is unsafe."""

    assert translate_etymologies(sections) is None  # type: ignore[arg-type]


def test_batch_limits_section_count_and_total_size() -> None:
    """Bound aggregate work even when each source section is individually valid."""

    assert translate_etymologies(["Unknown."] * 33) is None
    assert translate_etymologies(["Unknown." + " " * 9_990] * 6) is None


def test_batch_preserves_duplicates() -> None:
    """Do not infer that repeated source sections are semantically redundant."""

    assert translate_etymologies(["Unknown.", "Unknown."]) == [
        "Tsy fantatra ny fiaviany.",
        "Tsy fantatra ny fiaviany.",
    ]


def test_etymology_gloss_prefers_dictionary_translation(mocker) -> None:
    """Translate a gloss from the dictionary without invoking NLLB."""
    dictionary = mocker.patch(
        "api.translation_v2.functions.etymology.json_dictionary"
    )
    dictionary.online = True
    dictionary.look_up_dictionary.return_value = [
        {
            "definitions": [
                {"definition": "tantsaha", "language": "mg"},
            ]
        }
    ]
    nllb = mocker.patch(
        "api.translation_v2.functions.etymology.NllbDefinitionTranslation"
    )

    translated = translate_etymology(
        "Borrowed from {{bor|en|fr|paysan|t=peasant}}.",
        translate_glosses=True,
    )

    assert translated == (
        "Nindramina avy amin'ny {{fr}} ''paysan'' "
        "(midika hoe ''tantsaha'' (anglisy: ''peasant''))."
    )
    nllb.assert_not_called()


def test_etymology_gloss_falls_back_to_nllb(mocker) -> None:
    """Use validated NLLB output when the dictionary has no translation."""
    dictionary = mocker.patch(
        "api.translation_v2.functions.etymology.json_dictionary"
    )
    dictionary.online = False
    nllb = mocker.patch(
        "api.translation_v2.functions.etymology.NllbDefinitionTranslation"
    )
    nllb.return_value.get_translation.return_value = "tantsaha"

    translated = translate_etymology(
        "Borrowed from {{bor|en|fr|paysan|t=peasant}}.",
        translate_glosses=True,
    )

    assert translated == (
        "Nindramina avy amin'ny {{fr}} ''paysan'' "
        "(midika hoe ''tantsaha'' (anglisy: ''peasant''))."
    )
    nllb.return_value.get_translation.assert_called_once_with("peasant")


def test_etymology_gloss_labels_unsatisfactory_english_fallback(mocker) -> None:
    """Label the source language when no safe Malagasy gloss is available."""
    dictionary = mocker.patch(
        "api.translation_v2.functions.etymology.json_dictionary"
    )
    dictionary.online = False
    nllb = mocker.patch(
        "api.translation_v2.functions.etymology.NllbDefinitionTranslation"
    )
    nllb.return_value.get_translation.return_value = "peasant"

    translated = translate_etymology(
        "Borrowed from {{bor|en|fr|paysan|t=peasant}}.",
        translate_glosses=True,
    )

    assert translated == (
        "Nindramina avy amin'ny {{fr}} ''paysan'' "
        "(midika hoe ''peasant'' amin'ny teny anglisy)."
    )
