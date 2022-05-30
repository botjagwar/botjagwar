import re

import requests

try:
    import nltk
except ImportError:
    nltk = None
else:
    f = open('api/parsers/grammar.bnf', 'r')
    bnf = f.read()
    grammar = nltk.CFG.fromstring(bnf)
    f.close()


class ParserError(Exception):
    pass


class EnglishParser:
    def __init__(self):
        if nltk is None:
            raise NotImplementedError(
                'Cannot use EnglishParser as nltk module is not installed.')

        self.parser = nltk.ChartParser(grammar)
        self.parsed = 0
        self.processed = 0
        self.errors = 0
        self.abort = 0
        self.lp = 0

    def xml(self, parsed, tokens: list = None, lvl=0):
        xml_str = ''
        if tokens is None:
            tokens = []

        def _recursive_xml(parsed, tokens: list = None, lvl: int=0):
            if tokens is None:
                tokens = []

            _xml_str = ''
            for p in parsed:
                if isinstance(p, nltk.tree.Tree):
                    if isinstance(p[0], str):
                        _xml_str += '\n' + ' ' * 1 * lvl + \
                            f'<{p._label} word="{tokens[self.lp]}">'
                        setattr(p, 'word', tokens[self.lp])
                        self.lp += 1
                    else:
                        _xml_str += '\n' + ' ' * 1 * lvl + f'<{p._label}>'

                    _xml_str += _recursive_xml(p, tokens, lvl + 1)
                    _xml_str += '\n' + ' ' * 1 * lvl + f'</{p._label}>'

            return _xml_str

        xml_str += '<?xml version="1.0" encoding="UTF-8"?>'
        xml_str += '\n<tree>'
        xml_str += _recursive_xml(parsed, tokens, lvl + 1)
        xml_str += '\n</tree>\n'
        return xml_str

    def process(self, d):
        if not self.processed % 100:
            print(self.processed)

        s = d
        k = nltk.pos_tag(nltk.word_tokenize(s))
        try:
            parsed = self.parser.parse([y for x, y in k])
        except ValueError as err:
            raise ParserError() from err
        else:
            if parsed is None:
                raise ParserError()
            else:
                return parsed

    def preprocess(self, d):
        d = d.replace("''", '')
        d = d.replace('"', '')
        d = d.replace('``', '')
        d = re.sub('<([a-z]+)>', '', d)
        d = re.sub('<(/[a-z]+)>', '', d)

        return d

    def check_phrase_coverage(self):
        url = 'http://localhost:8100/definitions?definition_language=eq.en'
        data = [d["definition"] for d in requests.get(url).json()]

        for d in data[:5000]:
            if len(d) > 100:
                self.abort += 1
                continue
            try:
                d = self.preprocess(d)
                self.lp = 0
                tokens = nltk.word_tokenize(d)
                if len(tokens) < 2:
                    continue

                print(tokens)
                self.processed += 1
                pd = self.process(d)
                self.parsed += 1
                #print(q.xml(pd, tokens))
            except ParserError:
                self.errors += 1
                print(d)
                continue


if __name__ == '__main__':
    if nltk is None:
        raise NotImplementedError(
            'Cannot run phrase_parser as nltk module is not installed.')

    english_parser = EnglishParser()
    k = """sowing evil and reaping evil."""
    parsed = english_parser.process(k)
    tokens = nltk.word_tokenize(k)

    print(tokens)
    for i in parsed:
        i.pretty_print()
    print(english_parser.xml(parsed, tokens))
    # q.check_phrase_coverage()
    print(
        '%.2f %% rate' %
        (100. *
         english_parser.parsed /
         english_parser.processed))
    print(english_parser.errors, 'errors')
    print(english_parser.abort, 'aborts')
    print(f'{english_parser.parsed}/{english_parser.processed}')
