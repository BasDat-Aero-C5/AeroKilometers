from django.contrib import messages
from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render

from modules.green.models import Penyedia

from .forms import HadiahForm, MitraEditForm, MitraForm
from .models import Hadiah, Mitra


def _generate_kode_hadiah():
    last_code = Hadiah.objects.aggregate(Max('kode_hadiah'))['kode_hadiah__max']
    if not last_code:
        return 'RWD-001'

    try:
        next_number = int(last_code.split('-')[-1]) + 1
    except ValueError:
        next_number = Hadiah.objects.count() + 1

    return f"RWD-{next_number:03d}"


def daftar_hadiah(request):
    hadiah = Hadiah.objects.select_related('id_penyedia').order_by('kode_hadiah')
    penyedia = Penyedia.objects.all().order_by('id')
    penyedia_filter = request.GET.get('penyedia', '')
    status_filter = request.GET.get('status', '')

    if penyedia_filter:
        hadiah = hadiah.filter(id_penyedia_id=penyedia_filter)

    if status_filter == 'aktif':
        hadiah = [item for item in hadiah if item.is_active]
    elif status_filter == 'tidak_aktif':
        hadiah = [item for item in hadiah if not item.is_active]

    return render(request, 'hadiah/daftar_hadiah.html', {
        'hadiah_list': hadiah,
        'penyedia_list': penyedia,
        'penyedia_filter': penyedia_filter,
        'status_filter': status_filter,
    })


def tambah_hadiah(request):
    if request.method == 'POST':
        form = HadiahForm(request.POST)
        if form.is_valid():
            hadiah = form.save(commit=False)
            hadiah.kode_hadiah = _generate_kode_hadiah()
            hadiah.save()
            messages.success(request, 'Hadiah berhasil ditambahkan.')
            return redirect('red:daftar_hadiah')
    else:
        form = HadiahForm()

    return render(request, 'hadiah/tambah_hadiah.html', {'form': form})


def edit_hadiah(request, kode_hadiah):
    hadiah = get_object_or_404(Hadiah, pk=kode_hadiah)

    if request.method == 'POST':
        form = HadiahForm(request.POST, instance=hadiah)
        if form.is_valid():
            form.save()
            messages.success(request, 'Hadiah berhasil diperbarui.')
            return redirect('red:daftar_hadiah')
    else:
        form = HadiahForm(instance=hadiah)

    return render(request, 'hadiah/edit_hadiah.html', {
        'form': form,
        'hadiah': hadiah,
    })


def hapus_hadiah(request, kode_hadiah):
    hadiah = get_object_or_404(Hadiah, pk=kode_hadiah)

    if hadiah.is_active:
        messages.error(request, 'Hadiah yang masih aktif tidak dapat dihapus.')
        return redirect('red:daftar_hadiah')

    if request.method == 'POST':
        hadiah.delete()
        messages.success(request, 'Hadiah berhasil dihapus.')
        return redirect('red:daftar_hadiah')

    return render(request, 'hadiah/hapus_hadiah.html', {'hadiah': hadiah})


def daftar_mitra(request):
    mitra = Mitra.objects.select_related('id_penyedia').order_by('nama_mitra')
    return render(request, 'mitra/daftar_mitra.html', {'mitra_list': mitra})


def tambah_mitra(request):
    if request.method == 'POST':
        form = MitraForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                penyedia = Penyedia.objects.create()
                mitra = form.save(commit=False)
                mitra.id_penyedia = penyedia
                mitra.save()
            messages.success(request, 'Mitra berhasil didaftarkan.')
            return redirect('red:daftar_mitra')
    else:
        form = MitraForm()

    return render(request, 'mitra/tambah_mitra.html', {'form': form})


def edit_mitra(request, email_mitra):
    mitra = get_object_or_404(Mitra, pk=email_mitra)

    if request.method == 'POST':
        form = MitraEditForm(request.POST, instance=mitra)
        if form.is_valid():
            form.save()
            messages.success(request, 'Data mitra berhasil diperbarui.')
            return redirect('red:daftar_mitra')
    else:
        form = MitraEditForm(instance=mitra)

    return render(request, 'mitra/edit_mitra.html', {
        'form': form,
        'mitra': mitra,
    })


def hapus_mitra(request, email_mitra):
    mitra = get_object_or_404(Mitra, pk=email_mitra)

    if request.method == 'POST':
        mitra.id_penyedia.delete()
        messages.success(request, 'Mitra berhasil dihapus.')
        return redirect('red:daftar_mitra')

    return render(request, 'mitra/hapus_mitra.html', {'mitra': mitra})
