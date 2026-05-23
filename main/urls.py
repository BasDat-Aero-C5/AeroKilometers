from django.urls import path
from main.views import dashboard_member, dashboard_staff, homepage, login, logout, profile_view, register

app_name = 'main'

urlpatterns = [
    path('', homepage, name='home'),
    path('login/', login, name='login'),
    path('logout/', logout, name='logout'),
    path('register/', register, name='register'),
    path('profile/', profile_view, name='profile'),
    path('dashboard/', dashboard_member, name='dashboard_member'),
    path('staff/dashboard/', dashboard_staff, name='dashboard_staff'),
]
