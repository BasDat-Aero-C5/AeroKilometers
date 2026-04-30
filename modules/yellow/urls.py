from django.urls import path
from modules.yellow import views

app_name = 'yellow'

urlpatterns = [
    path('page/', views.page_view, name='page'),
    path('form/', views.form_view, name='form'),
]