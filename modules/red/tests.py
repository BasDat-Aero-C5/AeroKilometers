from datetime import date

from django.test import TestCase
from django.urls import reverse

from modules.green.models import Penyedia

from .models import Hadiah, Mitra


class RedCrudTests(TestCase):
    def test_create_mitra_creates_penyedia(self):
        response = self.client.post(reverse('red:tambah_mitra'), {
            'nama_mitra': 'Traveloka',
            'email_mitra': 'partnership@traveloka.com',
            'tanggal_kerja_sama': '2026-01-15',
        })

        self.assertRedirects(response, reverse('red:daftar_mitra'))
        mitra = Mitra.objects.get(email_mitra='partnership@traveloka.com')
        self.assertEqual(mitra.nama_mitra, 'Traveloka')
        self.assertTrue(Penyedia.objects.filter(pk=mitra.id_penyedia_id).exists())

    def test_create_hadiah_generates_code(self):
        penyedia = Penyedia.objects.create()

        response = self.client.post(reverse('red:tambah_hadiah'), {
            'nama_hadiah': 'Voucher Lounge',
            'id_penyedia': penyedia.pk,
            'harga_miles': 5000,
            'deskripsi': 'Akses lounge premium.',
            'valid_start_date': '2026-01-01',
            'program_end': '2026-12-31',
        })

        self.assertRedirects(response, reverse('red:daftar_hadiah'))
        hadiah = Hadiah.objects.get(kode_hadiah='RWD-001')
        self.assertEqual(hadiah.nama_hadiah, 'Voucher Lounge')

    def test_active_hadiah_cannot_be_deleted(self):
        penyedia = Penyedia.objects.create()
        hadiah = Hadiah.objects.create(
            kode_hadiah='RWD-001',
            id_penyedia=penyedia,
            nama_hadiah='Voucher Lounge',
            harga_miles=5000,
            deskripsi='Akses lounge premium.',
            valid_start_date=date(2026, 1, 1),
            program_end=date(2026, 12, 31),
        )

        response = self.client.post(reverse('red:hapus_hadiah', args=[hadiah.pk]))

        self.assertRedirects(response, reverse('red:daftar_hadiah'))
        self.assertTrue(Hadiah.objects.filter(pk=hadiah.pk).exists())
