from django.urls import path
from . import views

app_name = 'blue'

urlpatterns = [
    path('', views.redeem_hadiah, name='blue_home'),
    path('redeem/', views.redeem_hadiah, name='redeem_hadiah'),
    path('packages/', views.package_list, name='package_list'),
]