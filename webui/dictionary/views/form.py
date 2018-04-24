from django.template.loader import render_to_string
from .base import View
from ..models import Form


class FormView(View):
    def __init__(self, model: Form, target: str, request_ctxt, submit_button_label="Submit"):
        super(FormView, self).__init__(template_name='form.html')
        self.model = model
        self.target = target
        self.submit_button_label = submit_button_label
        self.request_ctxt = request_ctxt

    def render(self):
        params = {
            'submit_button_label': self.submit_button_label,
            'target': self.target,
            'form': self.model
        }
        return render_to_string(
            self.template_name,
            context=params,
            request=self.request_ctxt
        )
