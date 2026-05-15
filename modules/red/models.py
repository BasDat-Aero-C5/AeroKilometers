from django.db import models
from django.utils import timezone

from modules.green.models import Penyedia


class Mitra(models.Model):
    email_mitra = models.EmailField(max_length=100, primary_key=True)
    id_penyedia = models.OneToOneField(
        Penyedia,
        on_delete=models.CASCADE,
        db_column='id_penyedia',
        related_name='mitra',
    )
    nama_mitra = models.CharField(max_length=100)
    tanggal_kerja_sama = models.DateField()

    class Meta:
        db_table = 'MITRA'

    def __str__(self):
        return self.nama_mitra


class Hadiah(models.Model):
    kode_hadiah = models.CharField(max_length=10, primary_key=True)
    id_penyedia = models.ForeignKey(
        Penyedia,
        on_delete=models.CASCADE,
        db_column='id_penyedia',
        related_name='hadiah',
    )
    nama_hadiah = models.CharField(max_length=100)
    harga_miles = models.PositiveIntegerField()
    deskripsi = models.TextField()
    valid_start_date = models.DateField()
    program_end = models.DateField()

    class Meta:
        db_table = 'HADIAH'

    def __str__(self):
        return f"{self.kode_hadiah} - {self.nama_hadiah}"

    @property
    def is_active(self):
        today = timezone.localdate()
        return self.valid_start_date <= today <= self.program_end

    @property
    def penyedia_nama(self):
        mitra = getattr(self.id_penyedia, 'mitra', None)
        if mitra:
            return mitra.nama_mitra

        maskapai = getattr(self.id_penyedia, 'maskapai_set', None)
        if maskapai:
            first_maskapai = maskapai.first()
            if first_maskapai:
                return first_maskapai.nama_maskapai

        return f"Penyedia {self.id_penyedia_id}"
