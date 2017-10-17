# coding: utf8

from HTMLParser import HTMLParser


class MLStripper(HTMLParser):
    """
    Fanalana tag HTML amin'ny lahatsoratra iray.
    """
    def __init__(self):
        HTMLParser.__init__()
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()
