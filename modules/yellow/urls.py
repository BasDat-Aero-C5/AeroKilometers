from django.urls import path
from modules.yellow import views

app_name = 'yellow'

urlpatterns = [
    path('page/', views.page_view, name='page'),
    path('staff/page/', views.staff_page_view, name='staff_page'),
    path('form/staff/', views.form_view_staff, name='form_staff'),
    path('form/member/', views.form_view_member, name='form_member'),
]