from django.urls import path
from modules.yellow import views

app_name = 'yellow'

urlpatterns = [
    # Member routes
    path('page/', views.page_view, name='page'),
    path('form/member/', views.form_view_member, name='form_member'),
    path('edit/member/<str:id>/', views.edit_view_member, name='edit_member'),
    
    # Staff routes
    path('staff/page/', views.staff_page_view, name='staff_page'),
    path('staff/form/', views.form_view_staff, name='form_staff'),
    path('staff/edit/<str:id>/', views.edit_view_staff, name='edit_staff'),
]