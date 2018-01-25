
def parse_one_parameter_template(template_name=u'plural of'):
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
            return template_name, lemma, u'', u''
        else:
            raise ValueError(u"Unrecognised template: expected '%s' but got '%s'" % (parts[0], template_name))

    return _parse_one_parameter_template


def parse_inflection_of(template_expression):
    for char in u'{}':
        template_expression = template_expression.replace(char, u'')
    parts = template_expression.split(u'|')
    for tparam in parts:
        if tparam.find(u'=') != -1:
            parts.remove(tparam)
    t_name, lemma, _, case_name, number_ = parts[:5]
    return t_name, lemma, case_name, number_