from api.model.word import Entry


class PageRenderer(object):
    def render(self, info: Entry) -> str:
        raise NotImplementedError()

    def delete_section(self, section_name, wiki_page):
        raise NotImplementedError()
