from django.urls import path
from . import views

app_name = 'blue'

urlpatterns = [
    path('', views.redeem_hadiah, name='blue_home'),
    path('redeem/', views.redeem_hadiah, name='redeem_hadiah'),
    path('redeem/confirm/', views.redeem_confirm, name='redeem_confirm'),
    path('packages/', views.package_list, name='package_list'),
    path('packages/buy/', views.buy_package, name='buy_package'),
    path('tier/', views.tier_info, name='tier_info'),
    path('report/', views.report_view, name='report_view'),
]