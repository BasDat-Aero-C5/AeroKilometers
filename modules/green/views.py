from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import IntegrityError
from django.utils import timezone

from modules.green.models import (
    Member, Staf, Maskapai, Bandara,
    ClaimMissingMiles, Pengguna, Transfer
)


# Helper

def get_member(request):
    """Return Member object for the logged-in user, or None."""
    email = request.session.get('email')
    if not email:
        return None
    try:
        return Member.objects.select_related('email', 'id_tier').get(email=email)
    except Member.DoesNotExist:
        return None


def get_staf(request):
    """Return Staf object for the logged-in user, or None."""
    email = request.session.get('email')
    if not email:
        return None
    try:
        return Staf.objects.select_related('email', 'kode_maskapai').get(email=email)
    except Staf.DoesNotExist:
        return None


def login_required_member(view_func):
    """Decorator: redirect to login if not a Member."""
    def wrapper(request, *args, **kwargs):
        if not get_member(request):
            messages.error(request, 'Silakan login sebagai Member terlebih dahulu.')
            return redirect('main:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def login_required_staf(view_func):
    """Decorator: redirect to login if not Staf."""
    def wrapper(request, *args, **kwargs):
        if not get_staf(request):
            messages.error(request, 'Silakan login sebagai Staf terlebih dahulu.')
            return redirect('main:login')
        return view_func(request, *args, **kwargs)
    return wrapper


#  FITUR 8 - Claim Missing Miles (MEMBER)

#@login_required_member
def claim_list(request):
    """R — Riwayat klaim milik member, dengan filter status."""
    member = get_member(request)
    status_filter = request.GET.get('status', 'Semua')

    claims = ClaimMissingMiles.objects.filter(
        email_member=member
    ).select_related('maskapai', 'bandara_asal', 'bandara_tujuan').order_by('-timestamp')

    if status_filter in ['Menunggu', 'Disetujui', 'Ditolak']:
        claims = claims.filter(status_penerimaan=status_filter)

    context = {
        'member':        member,
        'claims':        claims,
        'status_filter': status_filter,
        'status_choices': ['Semua', 'Menunggu', 'Disetujui', 'Ditolak'],
    }
    return render(request, 'claim/claim_list.html', context)


#@login_required_member
def claim_create(request):
    """C — Ajukan klaim baru."""
    member    = get_member(request)
    maskapais = Maskapai.objects.all().order_by('nama_maskapai')
    bandaras  = Bandara.objects.all().order_by('iata_code')
    kelas_choices = ClaimMissingMiles.KELAS_CHOICES

    if request.method == 'POST':
        maskapai_kode       = request.POST.get('maskapai')
        bandara_asal_kode   = request.POST.get('bandara_asal')
        bandara_tujuan_kode = request.POST.get('bandara_tujuan')
        tanggal_penerbangan = request.POST.get('tanggal_penerbangan')
        flight_number       = request.POST.get('flight_number', '').strip().upper()
        nomor_tiket         = request.POST.get('nomor_tiket', '').strip()
        kelas_kabin         = request.POST.get('kelas_kabin')
        pnr                 = request.POST.get('pnr', '').strip().upper()

        # Basic validation
        if not all([maskapai_kode, bandara_asal_kode, bandara_tujuan_kode,
                    tanggal_penerbangan, flight_number, nomor_tiket, kelas_kabin, pnr]):
            messages.error(request, 'Semua field wajib diisi.')
            return render(request, 'claim/claim_form.html', {
                'member': member, 'maskapais': maskapais,
                'bandaras': bandaras, 'kelas_choices': kelas_choices,
            })

        if bandara_asal_kode == bandara_tujuan_kode:
            messages.error(request, 'Bandara asal dan tujuan tidak boleh sama.')
            return render(request, 'claim/claim_form.html', {
                'member': member, 'maskapais': maskapais,
                'bandaras': bandaras, 'kelas_choices': kelas_choices,
            })

        try:
            maskapai       = Maskapai.objects.get(pk=maskapai_kode)
            bandara_asal   = Bandara.objects.get(pk=bandara_asal_kode)
            bandara_tujuan = Bandara.objects.get(pk=bandara_tujuan_kode)

            ClaimMissingMiles.objects.create(
                email_member=member,
                maskapai=maskapai,
                bandara_asal=bandara_asal,
                bandara_tujuan=bandara_tujuan,
                tanggal_penerbangan=tanggal_penerbangan,
                flight_number=flight_number,
                nomor_tiket=nomor_tiket,
                kelas_kabin=kelas_kabin,
                pnr=pnr,
                status_penerimaan='Menunggu',
                timestamp=timezone.now(),
            )
            messages.success(request, 'Klaim berhasil diajukan dan sedang menunggu verifikasi.')
            return redirect('main:claim_list')

        except Maskapai.DoesNotExist:
            messages.error(request, 'Maskapai tidak valid.')
        except Bandara.DoesNotExist:
            messages.error(request, 'Bandara tidak valid.')
        except IntegrityError:
            messages.error(request, 'Klaim duplikat: kombinasi flight number, tanggal, dan nomor tiket sudah pernah diajukan.')

        return render(request, 'claim/claim_form.html', {
            'member': member, 'maskapais': maskapais,
            'bandaras': bandaras, 'kelas_choices': kelas_choices,
        })

    return render(request, 'claim/claim_form.html', {
        'member': member,
        'maskapais': maskapais,
        'bandaras': bandaras,
        'kelas_choices': kelas_choices,
    })


#@login_required_member
def claim_edit(request, pk):
    """U — Edit klaim, hanya jika status Menunggu."""
    member = get_member(request)
    claim  = get_object_or_404(ClaimMissingMiles, pk=pk, email_member=member)

    if claim.status_penerimaan != 'Menunggu':
        messages.error(request, 'Klaim yang sudah diproses tidak dapat diubah.')
        return redirect('main:claim_list')

    maskapais     = Maskapai.objects.all().order_by('nama_maskapai')
    bandaras      = Bandara.objects.all().order_by('iata_code')
    kelas_choices = ClaimMissingMiles.KELAS_CHOICES

    if request.method == 'POST':
        maskapai_kode       = request.POST.get('maskapai')
        bandara_asal_kode   = request.POST.get('bandara_asal')
        bandara_tujuan_kode = request.POST.get('bandara_tujuan')
        tanggal_penerbangan = request.POST.get('tanggal_penerbangan')
        flight_number       = request.POST.get('flight_number', '').strip().upper()
        nomor_tiket         = request.POST.get('nomor_tiket', '').strip()
        kelas_kabin         = request.POST.get('kelas_kabin')
        pnr                 = request.POST.get('pnr', '').strip().upper()

        if not all([maskapai_kode, bandara_asal_kode, bandara_tujuan_kode,
                    tanggal_penerbangan, flight_number, nomor_tiket, kelas_kabin, pnr]):
            messages.error(request, 'Semua field wajib diisi.')
            return render(request, 'claim/claim_form.html', {
                'member': member, 'claim': claim,
                'maskapais': maskapais, 'bandaras': bandaras,
                'kelas_choices': kelas_choices, 'is_edit': True,
            })

        if bandara_asal_kode == bandara_tujuan_kode:
            messages.error(request, 'Bandara asal dan tujuan tidak boleh sama.')
            return render(request, 'claim/claim_form.html', {
                'member': member, 'claim': claim,
                'maskapais': maskapais, 'bandaras': bandaras,
                'kelas_choices': kelas_choices, 'is_edit': True,
            })

        try:
            claim.maskapai           = Maskapai.objects.get(pk=maskapai_kode)
            claim.bandara_asal       = Bandara.objects.get(pk=bandara_asal_kode)
            claim.bandara_tujuan     = Bandara.objects.get(pk=bandara_tujuan_kode)
            claim.tanggal_penerbangan = tanggal_penerbangan
            claim.flight_number      = flight_number
            claim.nomor_tiket        = nomor_tiket
            claim.kelas_kabin        = kelas_kabin
            claim.pnr                = pnr
            claim.save()

            messages.success(request, 'Klaim berhasil diperbarui.')
            return redirect('main:claim_list')

        except IntegrityError:
            messages.error(request, 'Klaim duplikat: kombinasi flight number, tanggal, dan nomor tiket sudah pernah diajukan.')
            return render(request, 'claim/claim_form.html', {
                'member': member, 'claim': claim,
                'maskapais': maskapais, 'bandaras': bandaras,
                'kelas_choices': kelas_choices, 'is_edit': True,
            })

    return render(request, 'claim/claim_form.html', {
        'member':       member,
        'claim':        claim,
        'maskapais':    maskapais,
        'bandaras':     bandaras,
        'kelas_choices': kelas_choices,
        'is_edit':      True,
    })


#@login_required_member
def claim_delete(request, pk):
    """D — Batalkan klaim, hanya jika status Menunggu."""
    member = get_member(request)
    claim  = get_object_or_404(ClaimMissingMiles, pk=pk, email_member=member)

    if claim.status_penerimaan != 'Menunggu':
        messages.error(request, 'Klaim yang sudah diproses tidak dapat dibatalkan.')
        return redirect('main:claim_list')

    if request.method == 'POST':
        claim.delete()
        messages.success(request, 'Klaim berhasil dibatalkan.')
        return redirect('main:claim_list')

    # GET — show confirmation page
    return render(request, 'claim/claim_confirm_delete.html', {
        'member': member,
        'claim':  claim,
    })


#  FITUR 9 - Claim Missing Miles(STAF)

#@login_required_staf
def staf_claim_list(request):
    """R — Daftar semua klaim dari semua member, dengan filter."""
    staf = get_staf(request)

    status_filter   = request.GET.get('status', 'Semua')
    maskapai_filter = request.GET.get('maskapai', '')
    tgl_dari        = request.GET.get('tgl_dari', '')
    tgl_sampai      = request.GET.get('tgl_sampai', '')

    claims = ClaimMissingMiles.objects.select_related(
        'email_member', 'email_member__email',
        'maskapai', 'bandara_asal', 'bandara_tujuan', 'email_staf'
    ).order_by('-timestamp')

    if status_filter in ['Menunggu', 'Disetujui', 'Ditolak']:
        claims = claims.filter(status_penerimaan=status_filter)

    if maskapai_filter:
        claims = claims.filter(maskapai=maskapai_filter)

    if tgl_dari:
        claims = claims.filter(timestamp__date__gte=tgl_dari)

    if tgl_sampai:
        claims = claims.filter(timestamp__date__lte=tgl_sampai)

    maskapais = Maskapai.objects.all().order_by('nama_maskapai')

    context = {
        'staf':           staf,
        'claims':         claims,
        'maskapais':      maskapais,
        'status_filter':  status_filter,
        'maskapai_filter': maskapai_filter,
        'tgl_dari':       tgl_dari,
        'tgl_sampai':     tgl_sampai,
        'status_choices': ['Semua', 'Menunggu', 'Disetujui', 'Ditolak'],
    }
    return render(request, 'claim/staf_claim_list.html', context)


#@login_required_staf
def staf_claim_proses(request, pk):
    """U — Ubah status klaim menjadi Disetujui atau Ditolak."""
    staf  = get_staf(request)
    claim = get_object_or_404(ClaimMissingMiles, pk=pk)

    if claim.status_penerimaan != 'Menunggu':
        messages.error(request, 'Klaim ini sudah diproses sebelumnya.')
        return redirect('main:staf_claim_list')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action not in ['Disetujui', 'Ditolak']:
            messages.error(request, 'Aksi tidak valid.')
            return redirect('main:staf_claim_list')

        claim.status_penerimaan = action
        claim.email_staf        = staf
        claim.save()

        if action == 'Disetujui':
            # Add miles to member (placeholder values per kelas kabin)
            miles = ClaimMissingMiles.MILES_PER_KELAS.get(claim.kelas_kabin, 500)
            member = claim.email_member
            member.award_miles += miles
            member.total_miles += miles
            member.save()
            messages.success(
                request,
                f'Klaim disetujui. {miles} miles ditambahkan ke akun {member.email_id}.'
            )
        else:
            messages.success(request, 'Klaim telah ditolak.')

        return redirect('main:staf_claim_list')

    # GET — show confirmation modal page
    return render(request, 'claim/staf_claim_proses.html', {
        'staf':  staf,
        'claim': claim,
    })


# FITUR 10 — Transfer Miles

#@login_required_member
def transfer_list(request):
    """R — Riwayat transfer keluar dan masuk milik member."""
    member = get_member(request)

    transfers_keluar = Transfer.objects.filter(
        email_member_1=member
    ).select_related('email_member_2', 'email_member_2__email').order_by('-timestamp')

    transfers_masuk = Transfer.objects.filter(
        email_member_2=member
    ).select_related('email_member_1', 'email_member_1__email').order_by('-timestamp')

    # Gabungkan dan tandai tipe
    riwayat = []
    for t in transfers_keluar:
        riwayat.append({
            'timestamp': t.timestamp,
            'member_nama': f"{t.email_member_2.email.first_mid_name} {t.email_member_2.email.last_name}",
            'member_email': t.email_member_2_id, # Pastikan ini benar
            'jumlah': t.jumlah,
            'catatan': t.catatan,
            'tipe': 'Kirim',
        })
    for t in transfers_masuk:
        riwayat.append({
            'timestamp': t.timestamp,
            'member_nama': f"{t.email_member_1.email.first_mid_name} {t.email_member_1.email.last_name}",
            'member_email': t.email_member_1.email_id,
            'jumlah': t.jumlah,
            'catatan': t.catatan,
            'tipe': 'Terima',
        })

    # Sort by timestamp descending
    riwayat.sort(key=lambda x: x['timestamp'], reverse=True)

    context = {
        'member':  member,
        'riwayat': riwayat,
    }
    return render(request, 'transfer/transfer_list.html', context)


#@login_required_member
def transfer_create(request):
    """C — Buat transfer miles ke member lain."""
    member = get_member(request)

    if request.method == 'POST':
        email_penerima = request.POST.get('email_penerima', '').strip()
        jumlah_str     = request.POST.get('jumlah', '').strip()
        catatan        = request.POST.get('catatan', '').strip()

        # Validasi email penerima tidak kosong
        if not email_penerima or not jumlah_str:
            messages.error(request, 'Email penerima dan jumlah miles wajib diisi.')
            return render(request, 'transfer/transfer_form.html', {'member': member})

        # Validasi tidak transfer ke diri sendiri
        if email_penerima == member.email_id:
            messages.error(request, 'Anda tidak dapat mentransfer miles ke diri sendiri.')
            return render(request, 'transfer/transfer_form.html', {'member': member})

        # Validasi jumlah adalah angka positif
        try:
            jumlah = int(jumlah_str)
            if jumlah <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Jumlah miles harus berupa angka positif.')
            return render(request, 'transfer/transfer_form.html', {'member': member})

        # Validasi penerima adalah Member aktif
        try:
            penerima = Member.objects.select_related('email').get(email=email_penerima)
        except Member.DoesNotExist:
            messages.error(request, 'Email penerima tidak terdaftar sebagai Member aktif.')
            return render(request, 'transfer/transfer_form.html', {'member': member})

        # Validasi award miles mencukupi
        if member.award_miles < jumlah:
            messages.error(request, f'Award miles Anda tidak mencukupi. Tersedia: {member.award_miles} miles.')
            return render(request, 'transfer/transfer_form.html', {'member': member})

        # Buat transfer
        Transfer.objects.create(
            email_member_1=member,
            email_member_2=penerima,
            timestamp=timezone.now(),
            jumlah=jumlah,
            catatan=catatan if catatan else None,
        )

        # Kurangi award miles pengirim
        member.award_miles -= jumlah
        member.save()

        # Tambah award miles penerima
        penerima.award_miles += jumlah
        penerima.save()

        messages.success(request, f'{jumlah} miles berhasil ditransfer ke {email_penerima}.')
        return redirect('green:transfer_list')

    return render(request, 'transfer/transfer_form.html', {'member': member})