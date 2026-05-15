from django.db import models
from django.utils import timezone


class Pengguna(models.Model): #1
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
        managed = False
        db_table = 'PENGGUNA'

    def __str__(self):
        return self.email


class Tier(models.Model): #2
    id_tier                  = models.CharField(max_length=10, primary_key=True)
    nama                     = models.CharField(max_length=50)
    minimal_frekuensi_terbang = models.IntegerField()
    minimal_tier_miles       = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'TIER'

    def __str__(self):
        return self.nama


class Member(models.Model): #3
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
        managed = False
        db_table = 'MEMBER'

    def __str__(self):
        return f"{self.nomor_member} - {self.email_id}"


class Penyedia(models.Model): #4, (Provider)
    id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'PENYEDIA'

    def __str__(self):
        return f"Penyedia {self.id}"


class Maskapai(models.Model): #5, (Airline)
    kode_maskapai  = models.CharField(max_length=10, primary_key=True)
    nama_maskapai  = models.CharField(max_length=100)
    id_penyedia    = models.ForeignKey(
                        Penyedia,
                        on_delete=models.PROTECT,
                        db_column='id_penyedia'
                     )

    class Meta:
        managed = False
        db_table = 'MASKAPAI'

    def __str__(self):
        return f"{self.kode_maskapai} - {self.nama_maskapai}"


class Staf(models.Model): #6, (Staff)
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
        managed = False
        db_table = 'STAF'

    def __str__(self):
        return f"{self.id_staf} - {self.email_id}"

class Mitra(models.Model): #7, (Partner)
    email_mitra = models.CharField(max_length=100, primary_key=True)
    id_penyedia = models.ForeignKey(
                        Penyedia,
                        on_delete=models.PROTECT,
                        db_column='id_penyedia'
                    )
    nama_mitra   = models.CharField(max_length=100)
    tanggal_kerja_sama = models.DateField() #Not Null

    class Meta:
        managed = False
        db_table = 'MITRA'

    def __str__(self):
        return f"{self.id_mitra} - {self.nama}"
    
class Identitas(models.Model): #8, (Identity)
    nomor = models.CharField(max_length=50, primary_key=True)
    email_member = models.ForeignKey(
                        Member,
                        on_delete=models.CASCADE,
                        db_column='email_member',
                        related_name='identitas'
                    )
    tanggal_habis = models.DateField() #Not Null
    tanggal_terbit = models.DateField() #Not Null
    negara_penerbit = models.CharField(max_length=50) #Not Null
    jenis = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'IDENTITAS'

    def __str__(self):
        return f"{self.nomor} - {self.email_member_id}"

class AwardMilesPackage(models.Model): #9, (Miles Package)
    id_package   = models.CharField(max_length=20, primary_key=True) #Auto increment with format AMP-XXX
    jumlah_miles = models.IntegerField()
    harga        = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'AWARD_MILES_PACKAGE'

    def __str__(self):
        return f"{self.id_package} - {self.nama} | {self.jumlah_miles} miles for ${self.harga}"

class MemberAwardMilesPackage(models.Model): #10, (Member's Purchased Miles Package)
    email_member = models.ForeignKey(
                        Member,
                        on_delete=models.CASCADE,
                        db_column='email_member',
                        related_name='miles_packages'
                    )
    id_package   = models.ForeignKey(
                        AwardMilesPackage,
                        on_delete=models.PROTECT,
                        db_column='id_package'
                    ) # Not Null
    timestamp    = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'MEMBER_AWARD_MILES_PACKAGE'
        unique_together = [['email_member', 'id_package', 'timestamp']]

    def __str__(self):
        return f"{self.email_member_id} bought {self.id_package_id} at {self.timestamp}"

class Bandara(models.Model): #10, (Airport)
    iata_code = models.CharField(max_length=3, primary_key=True)
    nama      = models.CharField(max_length=100)
    kota      = models.CharField(max_length=100)
    negara    = models.CharField(max_length=100)

    class Meta:
        managed = False
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
        ('First',           'First'),
    ]

    # Miles awarded per kelas kabin (placeholder — update when spec is available)
    MILES_PER_KELAS = {
        'Economy':         500,
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
        managed = False
        db_table = 'CLAIM_MISSING_MILES'
        # Prevent duplicate claims
        unique_together = [['email_member', 'flight_number', 'tanggal_penerbangan', 'nomor_tiket']]

    def __str__(self):
        return f"CLM-{self.pk:03d} | {self.email_member_id} | {self.status_penerimaan}"

    def get_nomor_klaim(self):
        return f"CLM-{self.pk:03d}"


class Transfer(models.Model): #13
    email_member_1 = models.ForeignKey(
                         Member,
                         on_delete=models.CASCADE,
                         db_column='email_member_1',
                         related_name='transfers_keluar'
                     )
    email_member_2 = models.ForeignKey(
                         Member,
                         on_delete=models.CASCADE,
                         db_column='email_member_2',
                         related_name='transfers_masuk'
                     )
    timestamp = models.DateTimeField(default=timezone.now)
    jumlah    = models.IntegerField() #not null
    catatan   = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'TRANSFER'
        unique_together = [['email_member_1', 'email_member_2', 'timestamp']]

    def __str__(self):
        return f"{self.email_member_1_id} -> {self.email_member_2_id} | {self.jumlah} miles"
    
class Hadiah(models.Model): #14, (Reward)
    kode_hadiah   = models.CharField(max_length=20, primary_key=True) #Auto increment with format RWD-XXX
    nama        = models.CharField(max_length=100)
    jumlah_miles = models.IntegerField() #Not null
    deskripsi   = models.TextField()
    valid_start  = models.DateField() #Not Null
    program_end    = models.DateField() #not null
    id_penyedia    = models.ForeignKey(
                        Penyedia,
                        on_delete=models.PROTECT,
                        db_column='id_penyedia'
                        ) #not null
    
    class Meta:
        managed = False
        db_table = 'HADIAH'

    def __str__(self):
        return f"{self.id_hadiah} - {self.nama} | {self.jumlah_miles} miles | Stock: {self.stok}"

class Redeem(models.Model):
    email_member = models.ForeignKey(
                        Member,
                        on_delete=models.CASCADE,
                        db_column='email_member',
                        related_name='redeems'
                    )
    id_hadiah    = models.CharField(max_length=20)
    timestamp    = models.DateTimeField(default=timezone.now) #Primary Key
    status       = models.CharField(max_length=20, default='Menunggu')

    class Meta:
        managed = False
        db_table = 'REDEEM'

    def __str__(self):
        return f"Redeem {self.id} | {self.email_member_id} | {self.id_hadiah} | {self.status}"