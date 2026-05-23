# Generated manually for red module CRUD.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('green', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Mitra',
            fields=[
                ('email_mitra', models.EmailField(max_length=100, primary_key=True, serialize=False)),
                ('nama_mitra', models.CharField(max_length=100)),
                ('tanggal_kerja_sama', models.DateField()),
                ('id_penyedia', models.OneToOneField(db_column='id_penyedia', on_delete=django.db.models.deletion.CASCADE, related_name='mitra', to='green.penyedia')),
            ],
            options={
                'db_table': 'mitra',
            },
        ),
        migrations.CreateModel(
            name='Hadiah',
            fields=[
                ('kode_hadiah', models.CharField(max_length=10, primary_key=True, serialize=False)),
                ('nama_hadiah', models.CharField(max_length=100)),
                ('harga_miles', models.PositiveIntegerField()),
                ('deskripsi', models.TextField()),
                ('valid_start_date', models.DateField()),
                ('program_end', models.DateField()),
                ('id_penyedia', models.ForeignKey(db_column='id_penyedia', on_delete=django.db.models.deletion.CASCADE, related_name='hadiah', to='green.penyedia')),
            ],
            options={
                'db_table': 'hadiah',
            },
        ),
    ]
