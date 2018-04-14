from django.template.loader import render_to_string


class View(object):
    def __init__(self, template_name=None):
        self.template_name = template_name
        self.data = None

    def set_data(self, data):
        self.data = data

    def render(self):
        return render_to_string(self.template_name, context=self.data)


class TextView(View):
    def __init__(self, text):
        super(TextView, self).__init__(template_name='text_view.html')
        self.text = text

    def render(self):
        return render_to_string(self.template_name, context={
            'text': self.text,
        })


class SectionView(View):
    def __init__(self, name: str, level=1):
        super(SectionView, self).__init__()
        self.views = []
        self.name = name
        self.set_level(level)
        self.section_head_template = 'section_head_view.html'
        self.section_content_template = 'section_content_view.html'

    def add_view(self, view: View):
        self.views.append(view)

    def set_level(self, level: int):
        if 0 < level <= 7:
            self.level = level
        else:
            raise ValueError('Expected a integer in interval [1; 7]')

    def render(self):
        ret_string = ''
        section_view_number = 1
        ret_string += render_to_string(self.section_head_template, context={
            'level': self.level,
            'title': self.name
        })
        for view in self.views:
            section_view_number += 1
            if isinstance(view, SectionView):
                view.set_level(self.level + 1)

            ret_string += render_to_string(self.section_content_template, context={
                'content': view.render(),
                'id': '%s_%d' % (view.__class__.__name__, section_view_number)
            })

        return ret_string


class PageView(object):
    def __init__(self, title='', template='page_view.html'):
        self.title = title
        self.template_name = template
        self.sections = []
        self.data = None

    def set_data(self, data):
        self.data = data

    def add_section(self, section: SectionView):
        self.sections.append(section)

    def render(self):
        body = ''
        for section in self.sections:
            body += section.render()

        return render_to_string(self.template_name, context={
            'title': self.title,
            'body': body})