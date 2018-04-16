from django.urls import path

from . import views

urlpatterns = [
    path('word_list', views.word_list_view, name='word_list'),
    path('word', views.word_view, name='word'),
    path('delete_word', views.delete_word, name='delete_word'),
]