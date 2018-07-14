from django.urls import path

from .controllers import handlers as controller_handlers
from .views import handlers as view_handlers

urlpatterns = [
    path('Word/list', view_handlers.word_list_view, name='wordlist'),
    path('Word/view', view_handlers.word_view, name='word'),
    path('Word/edit', controller_handlers.word_edit, name='wordedit'),
    path('Word/delete', controller_handlers.delete_word, name='worddelete'),

    path('Definition/edit', controller_handlers.definition_edit, name='definitionedit'),
    path('Definition/delete', controller_handlers.definition_delete, name='definitiondelete'),
]