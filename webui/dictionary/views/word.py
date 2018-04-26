from .base import SectionView


class WordView(SectionView):
    def __init__(self, word: dict):
        """
        :param word: Word
        """
        super(WordView, self).__init__(word['word'])

    def render(self):
        pass


