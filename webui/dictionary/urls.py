from django.urls import path

from . import views

urlpatterns = [
    path('word_list', views.word_view, name='word_list'),
]