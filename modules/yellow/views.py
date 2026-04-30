from django.shortcuts import render
from modules.green.models import (
    Member, Staf, Maskapai, Bandara,
    ClaimMissingMiles, Pengguna
)

# Create your views here.

def page_view(request):
    identities = [
        {
            'nomor_dokumen': 'A12345678',
            'jenis_dokumen': 'Paspor',
            'negara': 'Indonesia',
            'tanggal_terbit': '2020-01-15',
            'tanggal_habis': '2030-01-15',
            'status': 'Aktif',
        },
        {
            'nomor_dokumen': '3275012345678901',
            'jenis_dokumen': 'KTP',
            'negara': 'Indonesia',
            'tanggal_terbit': '2019-06-01',
            'tanggal_habis': '2024-06-01',
            'status': 'Kedaluwarsa',
        },
    ]

    return render(request, 'member/page.html', {
        'identities': identities,
    })


def staff_page_view(request):
    members = [
        {
            'id': '1',
            'nomor_member': 'M0001',
            'nama': 'Mr. John William Doe',
            'email': 'john@example.com',
            'tier': 'Gold',
            'total_miles': 45000,
            'award_miles': 32000,
            'tanggal_bergabung': '2024-01-15',
        },
        {
            'id': '2',
            'nomor_member': 'M0002',
            'nama': 'Mrs. Jane Smith',
            'email': 'jane@example.com',
            'tier': 'Silver',
            'total_miles': 20000,
            'award_miles': 15000,
            'tanggal_bergabung': '2024-03-10',
        },
    ]

    return render(request, 'member/staff_page.html', {
        'members': members,
    })


def form_view_staff(request):
    ## Authentication required
    if request.method == 'POST':
        pass

    return render(request, 'member/form_create_staff.html')

def form_view_member(request):
    ## Authentication required
    if request.method == 'POST':
        pass

    return render(request, 'member/form_create_member.html')


