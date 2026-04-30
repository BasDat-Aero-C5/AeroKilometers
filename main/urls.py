from django.urls import path
from main.views import homepage, login, register, dashboard_member, dashboard_staff

app_name = 'main'

urlpatterns = [
    path('', homepage, name='home'),
    path('login/', login, name='login'),
    path('register/', register, name='register'),
    path('dashboard/', dashboard_member, name='dashboard_member'),
    path('staff/dashboard/', dashboard_staff, name='dashboard_staff'),
]