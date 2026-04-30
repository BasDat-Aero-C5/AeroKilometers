from django.db import models
from django.utils import timezone


class Pengguna(models.Model):
    SALUTATION_CHOICES = [
        ('Mr.', 'Mr.'),
        ('Mrs.', 'Mrs.'),
        ('Ms.', 'Ms.'),
        ('Dr.', 'Dr.'),
    ]
    email           = models.CharField(max_length=100, primary_key=True)
    password        = models.CharField(max_length=255)
    salutation      = models.CharField(max_length=10, choices=SALUTATION_CHOICES)
    first_mid_name  = models.CharField(max_length=100)
    last_name       = models.CharField(max_length=100)
    country_code    = models.CharField(max_length=5)
    mobile_number   = models.CharField(max_length=20)
    tanggal_lahir   = models.DateField()
    kewarganegaraan = models.CharField(max_length=50)

    class Meta:
        db_table = 'PENGGUNA'

    def __str__(self):
        return self.email


class Tier(models.Model):
    id_tier                  = models.CharField(max_length=10, primary_key=True)
    nama                     = models.CharField(max_length=50)
    minimal_frekuensi_terbang = models.IntegerField()
    minimal_tier_miles       = models.IntegerField()

    class Meta:
        db_table = 'TIER'

    def __str__(self):
        return self.nama


class Member(models.Model):
    email             = models.OneToOneField(
                            Pengguna,
                            on_delete=models.CASCADE,
                            primary_key=True,
                            db_column='email'
                        )
    nomor_member      = models.CharField(max_length=20, unique=True)
    tanggal_bergabung = models.DateField()
    id_tier           = models.ForeignKey(
                            Tier,
                            on_delete=models.PROTECT,
                            db_column='id_tier'
                        )
    award_miles       = models.IntegerField(default=0)
    total_miles       = models.IntegerField(default=0)

    class Meta:
        db_table = 'MEMBER'

    def __str__(self):
        return f"{self.nomor_member} - {self.email_id}"


class Penyedia(models.Model):
    id = models.AutoField(primary_key=True)

    class Meta:
        db_table = 'PENYEDIA'

    def __str__(self):
        return f"Penyedia {self.id}"


class Maskapai(models.Model):
    kode_maskapai  = models.CharField(max_length=10, primary_key=True)
    nama_maskapai  = models.CharField(max_length=100)
    id_penyedia    = models.ForeignKey(
                        Penyedia,
                        on_delete=models.PROTECT,
                        db_column='id_penyedia'
                     )

    class Meta:
        db_table = 'MASKAPAI'

    def __str__(self):
        return f"{self.kode_maskapai} - {self.nama_maskapai}"


class Staf(models.Model):
    email         = models.OneToOneField(
                        Pengguna,
                        on_delete=models.CASCADE,
                        primary_key=True,
                        db_column='email'
                    )
    id_staf       = models.CharField(max_length=20, unique=True)
    kode_maskapai = models.ForeignKey(
                        Maskapai,
                        on_delete=models.PROTECT,
                        db_column='kode_maskapai'
                    )

    class Meta:
        db_table = 'STAF'

    def __str__(self):
        return f"{self.id_staf} - {self.email_id}"


class Bandara(models.Model):
    iata_code = models.CharField(max_length=3, primary_key=True)
    nama      = models.CharField(max_length=100)
    kota      = models.CharField(max_length=100)
    negara    = models.CharField(max_length=100)

    class Meta:
        db_table = 'BANDARA'

    def __str__(self):
        return f"{self.iata_code} - {self.nama}"


class ClaimMissingMiles(models.Model):
    STATUS_CHOICES = [
        ('Menunggu',  'Menunggu'),
        ('Disetujui', 'Disetujui'),
        ('Ditolak',   'Ditolak'),
    ]
    KELAS_CHOICES = [
        ('Economy',         'Economy'),
        ('Business',        'Business'),
        ('Premium Economy', 'Premium Economy'),
        ('First',           'First'),
    ]

    # Miles awarded per kelas kabin (placeholder — update when spec is available)
    MILES_PER_KELAS = {
        'Economy':         500,
        'Premium Economy': 750,
        'Business':        1000,
        'First':           1500,
    }

    email_member       = models.ForeignKey(
                             Member,
                             on_delete=models.CASCADE,
                             db_column='email_member',
                             related_name='claims'
                         )
    email_staf         = models.ForeignKey(
                             Staf,
                             on_delete=models.SET_NULL,
                             null=True,
                             blank=True,
                             db_column='email_staf',
                             related_name='handled_claims'
                         )
    maskapai           = models.ForeignKey(
                             Maskapai,
                             on_delete=models.PROTECT,
                             db_column='maskapai'
                         )
    bandara_asal       = models.ForeignKey(
                             Bandara,
                             on_delete=models.PROTECT,
                             db_column='bandara_asal',
                             related_name='claims_asal'
                         )
    bandara_tujuan     = models.ForeignKey(
                             Bandara,
                             on_delete=models.PROTECT,
                             db_column='bandara_tujuan',
                             related_name='claims_tujuan'
                         )
    tanggal_penerbangan = models.DateField()
    flight_number       = models.CharField(max_length=10)
    nomor_tiket         = models.CharField(max_length=20)
    kelas_kabin         = models.CharField(max_length=20, choices=KELAS_CHOICES)
    pnr                 = models.CharField(max_length=10)
    status_penerimaan   = models.CharField(
                              max_length=20,
                              choices=STATUS_CHOICES,
                              default='Menunggu'
                          )
    timestamp           = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'CLAIM_MISSING_MILES'
        # Prevent duplicate claims
        unique_together = [['email_member', 'flight_number', 'tanggal_penerbangan', 'nomor_tiket']]

    def __str__(self):
        return f"CLM-{self.pk:03d} | {self.email_member_id} | {self.status_penerimaan}"

    def get_nomor_klaim(self):
        return f"CLM-{self.pk:03d}"