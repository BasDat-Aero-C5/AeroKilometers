from django.shortcuts import render

def daftar_hadiah(request):
    return render(request, 'hadiah/daftar_hadiah.html')

def tambah_hadiah(request):
    return render(request, 'hadiah/tambah_hadiah.html')

def edit_hadiah(request):
    return render(request, 'hadiah/edit_hadiah.html')

def hapus_hadiah(request):
    return render(request, 'hadiah/hapus_hadiah.html')

def daftar_mitra(request):
    return render(request, 'mitra/daftar_mitra.html')

def tambah_mitra(request):
    return render(request, 'mitra/tambah_mitra.html')

def edit_mitra(request):
    return render(request, 'mitra/edit_mitra.html')

def hapus_mitra(request):
    return render(request, 'mitra/hapus_mitra.html')