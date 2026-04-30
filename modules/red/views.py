from django.shortcuts import render

def daftar_hadiah(request):
    return render(request, 'hadiah/daftar_hadiah.html')

def tambah_hadiah(request):
    return render(request, 'hadiah/tambah_hadiah.html')

def edit_hadiah(request):
    return render(request, 'hadiah/edit_hadiah.html')

def hapus_hadiah(request):
    return render(request, 'hadiah/hapus_hadiah.html')