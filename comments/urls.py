from django.urls import path

from . import views

app_name = 'comments'

urlpatterns = [
    path('<slug:slug>/comment/', views.add_comment, name='add_comment'),
]
