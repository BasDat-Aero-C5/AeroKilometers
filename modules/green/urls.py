from django.urls import path
from modules.green import views

app_name = 'green'

urlpatterns = [
    # Fitur 8 - Member
    path('claim/',                views.claim_list,   name='claim_list'),
    path('claim/ajukan/',         views.claim_create, name='claim_create'),
    path('claim/<int:pk>/edit/',  views.claim_edit,   name='claim_edit'),
    path('claim/<int:pk>/batal/', views.claim_delete, name='claim_delete'),

    # Fitur 9 - Staf
    path('staf/claim/',                  views.staf_claim_list,   name='staf_claim_list'),
    path('staf/claim/<int:pk>/proses/',  views.staf_claim_proses, name='staf_claim_proses'),
]