from django.urls import path
from main.views import homepage, login, register

app_name = 'main'

urlpatterns = [
    path('', homepage, name='home'),
    path('login/', login, name='login'),
    path('register/', register, name='register'),
]