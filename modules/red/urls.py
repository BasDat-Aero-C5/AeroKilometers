from django.urls import path
from . import views

app_name = 'red'

urlpatterns = [
    path('hadiah/', views.daftar_hadiah, name='daftar_hadiah'),
    path('hadiah/tambah/', views.tambah_hadiah, name='tambah_hadiah'),
    path('hadiah/edit/', views.edit_hadiah, name='edit_hadiah'),
    path('hadiah/hapus/', views.hapus_hadiah, name='hapus_hadiah'),
    path('mitra/', views.daftar_mitra, name='daftar_mitra'),
    path('mitra/tambah/', views.tambah_mitra, name='tambah_mitra'),
    path('mitra/edit/', views.edit_mitra, name='edit_mitra'),
    path('mitra/hapus/', views.hapus_mitra, name='hapus_mitra'),
]