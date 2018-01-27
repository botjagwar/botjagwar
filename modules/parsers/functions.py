# coding: utf8

from inflection_template import WordForm


def parse_one_parameter_template(template_name=u'plural of', case_name=u'', number=u's', gender=None):
    """
    Very generic code that can parse anything like {{plural of|xxyyzz}}, which is very common on en.wiktionary
    Use with caution, though.
    :param template_expression:
    :return: a function which sould return the contents of the template specified in template_name
    """
    def _parse_one_parameter_template(template_expression):
        for char in u'{}':
            template_expression = template_expression.replace(char, u'')
        parts = template_expression.split(u'|')
        lemma = parts[1]
        if parts[0] == template_name:
            return WordForm(lemma, case_name, number, gender=gender)
        else:
            raise ValueError(u"Unrecognised template: expected '%s' but got '%s'" % (parts[0], template_name))

    return _parse_one_parameter_template


def parse_lv_inflection_of(template_expression):
    """Example of recognised template:
        {{lv-inflection of|bagātīgs|dat|p|f||adj}}
       Should return 4 parameter """
    for char in u'{}':
        template_expression = template_expression.replace(char, u'')
    parts = template_expression.split(u'|')
    for tparam in parts:
        if tparam.find(u'=') != -1:
            parts.remove(tparam)
    t_name, lemma, case_name, number_, gender = parts[:5]
    return WordForm(lemma, case_name, number_, gender)


def parse_inflection_of(template_expression):
    for char in u'{}':
        template_expression = template_expression.replace(char, u'')
    parts = template_expression.split(u'|')
    for tparam in parts:
        if tparam.find(u'=') != -1:
            parts.remove(tparam)
    t_name, lemma, _, case_name, number_ = parts[:5]
    return WordForm(lemma, case_name, number_, gender=None)