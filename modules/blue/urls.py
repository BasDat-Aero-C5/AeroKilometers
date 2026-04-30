from django.urls import path
from modules.blue import views

app_name = 'blue'

urlpatterns = [
    path('', views.redeem_hadiah, name='blue_home'),
    path('redeem/', views.redeem_hadiah, name='redeem_hadiah'),
    path("packages/", views.package_page, name="package_page"),
    path("tier/", views.tier_page, name="tier_page"),
    path("report/", views.report_page, name="report_page"),
]