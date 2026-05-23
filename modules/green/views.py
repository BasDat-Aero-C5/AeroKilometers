from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import IntegrityError
from django.utils import timezone
from django.conf import settings
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from urllib.parse import urlparse

from modules.green.models import ClaimMissingMiles


class DBRow(dict):
    def __getattr__(self, name):
        if name in self:
            return self[name]
        if name == 'pk' and 'id' in self:
            return self['id']
        if name == 'email_id' and 'email' in self:
            return self['email']
        if name == 'get_nomor_klaim' and 'id' in self:
            return lambda: f"CLM-{self['id']:03d}"
        raise AttributeError(f"Attribute {name} not found")

    def __setattr__(self, name, value):
        self[name] = value


def get_db_connection():
    """Return a database connection for local SQLite or production Postgres."""
    if settings.PRODUCTION:
        db_url = os.environ.get('DATABASE_URL')
        parsed = urlparse(db_url)
        return psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            sslmode='require'
        )

    from django.db import connection
    return connection


def adapt_sql(sql):
    """Adapt placeholder syntax for SQLite vs PostgreSQL."""
    if settings.PRODUCTION:
        return sql
    return sql.replace('%s', '?')


def execute_raw_sql(sql, params=None):
    """Execute a raw SELECT query and return DBRow list."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if settings.PRODUCTION else conn.cursor()
        sql = adapt_sql(sql)
        cursor.execute(sql, params or [])
        rows = cursor.fetchall()

        if not settings.PRODUCTION:
            columns = [col[0] for col in cursor.description] if cursor.description else []
            rows = [DBRow(dict(zip(columns, row))) for row in rows]
        else:
            rows = [DBRow(row) for row in rows]

        cursor.close()
        if settings.PRODUCTION:
            conn.close()
        return rows
    except Exception as e:
        print(f"Database error: {e}")
        return []


def execute_raw_sql_update(sql, params=None):
    """Execute a raw INSERT/UPDATE/DELETE query and return affected rowcount."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = adapt_sql(sql)
        cursor.execute(sql, params or [])
        rowcount = cursor.rowcount
        conn.commit()
        cursor.close()
        if settings.PRODUCTION:
            conn.close()
        return rowcount
    except Exception as e:
        print(f"Database error: {e}")
        raise


def execute_raw_sql_many(commands):
    """Execute multiple SQL statements inside the same transaction."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for sql, params in commands:
            cursor.execute(adapt_sql(sql), params or [])
        conn.commit()
        rowcount = cursor.rowcount
        cursor.close()
        if settings.PRODUCTION:
            conn.close()
        return rowcount
    except Exception as e:
        conn.rollback()
        cursor.close()
        if settings.PRODUCTION:
            conn.close()
        print(f"Database transaction error: {e}")
        raise


def get_member(request):
    """Return Member data for the logged-in user, or None."""
    email = request.session.get('email')
    if not email:
        return None

    sql = """
        SELECT m.email, m.nomor_member, m.tanggal_bergabung, m.id_tier,
               m.award_miles, m.total_miles,
               p.first_mid_name, p.last_name,
               p.country_code, p.mobile_number,
               p.tanggal_lahir, p.kewarganegaraan,
               p.salutation,
               m.email as email_id
        FROM member m
        JOIN pengguna p ON m.email = p.email
        WHERE m.email = %s
    """
    result = execute_raw_sql(sql, [email])
    return result[0] if result else None


def get_staf(request):
    """Return Staf data for the logged-in user, or None."""
    email = request.session.get('email')
    if not email:
        return None

    sql = """
        SELECT s.email, s.id_staf, s.kode_maskapai,
               p.first_mid_name, p.last_name,
               p.country_code, p.mobile_number,
               p.tanggal_lahir, p.kewarganegaraan,
               p.salutation,
               s.email as email_id
        FROM staf s
        JOIN pengguna p ON s.email = p.email
        WHERE s.email = %s
    """
    result = execute_raw_sql(sql, [email])
    return result[0] if result else None


def login_required_member(view_func):
    def wrapper(request, *args, **kwargs):
        if not get_member(request):
            messages.error(request, 'Silakan login sebagai Member terlebih dahulu.')
            return redirect('main:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def login_required_staf(view_func):
    def wrapper(request, *args, **kwargs):
        if not get_staf(request):
            messages.error(request, 'Silakan login sebagai Staf terlebih dahulu.')
            return redirect('main:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def get_maskapai_list():
    sql = "SELECT kode_maskapai, nama_maskapai FROM maskapai ORDER BY nama_maskapai"
    return execute_raw_sql(sql)


def get_bandara_list():
    sql = "SELECT iata_code, nama, kota, negara FROM bandara ORDER BY iata_code"
    return execute_raw_sql(sql)


def get_maskapai_by_pk(kode_maskapai):
    sql = "SELECT kode_maskapai, nama_maskapai FROM maskapai WHERE kode_maskapai = %s"
    rows = execute_raw_sql(sql, [kode_maskapai])
    return rows[0] if rows else None


def get_bandara_by_pk(iata_code):
    sql = "SELECT iata_code, nama, kota, negara FROM bandara WHERE iata_code = %s"
    rows = execute_raw_sql(sql, [iata_code])
    return rows[0] if rows else None


def get_member_by_email(email):
    sql = "SELECT email, nomor_member, award_miles, total_miles, email as email_id FROM member WHERE email = %s"
    rows = execute_raw_sql(sql, [email])
    return rows[0] if rows else None


def get_claim_by_pk_and_member(pk, member_email):
    sql = """
        SELECT c.*, c.id as id
        FROM claim_missing_miles c
        WHERE c.id = %s AND c.email_member = %s
    """
    rows = execute_raw_sql(sql, [pk, member_email])
    return rows[0] if rows else None


def get_claim_by_pk(pk):
    sql = "SELECT c.*, c.id as id FROM claim_missing_miles c WHERE c.id = %s"
    rows = execute_raw_sql(sql, [pk])
    return rows[0] if rows else None


def build_claim_item(row):
    if not row:
        return None

    claim = DBRow(row)
    claim['maskapai'] = DBRow({
        'kode_maskapai': row['maskapai'],
        'nama_maskapai': row.get('maskapai_nama') or ''
    })
    claim['bandara_asal'] = DBRow({
        'iata_code': row['bandara_asal'],
        'nama': row.get('bandara_asal_nama') or '',
        'kota': row.get('bandara_asal_kota') or '',
        'negara': row.get('bandara_asal_negara') or '',
    })
    claim['bandara_tujuan'] = DBRow({
        'iata_code': row['bandara_tujuan'],
        'nama': row.get('bandara_tujuan_nama') or '',
        'kota': row.get('bandara_tujuan_kota') or '',
        'negara': row.get('bandara_tujuan_negara') or '',
    })
    return claim


@login_required_member
def claim_list(request):
    member = get_member(request)
    status_filter = request.GET.get('status', 'Semua')

    sql = """
        SELECT c.id, c.email_member, c.maskapai, c.bandara_asal, c.bandara_tujuan,
               c.tanggal_penerbangan, c.flight_number, c.nomor_tiket,
               c.kelas_kabin, c.pnr, c.status_penerimaan, c.timestamp,
               m.nama_maskapai as maskapai_nama,
               ba.nama as bandara_asal_nama, ba.kota as bandara_asal_kota, ba.negara as bandara_asal_negara,
               bt.nama as bandara_tujuan_nama, bt.kota as bandara_tujuan_kota, bt.negara as bandara_tujuan_negara
        FROM claim_missing_miles c
        JOIN maskapai m ON c.maskapai = m.kode_maskapai
        JOIN bandara ba ON c.bandara_asal = ba.iata_code
        JOIN bandara bt ON c.bandara_tujuan = bt.iata_code
        WHERE c.email_member = %s
    """
    params = [member.email_id]

    if status_filter in ['Menunggu', 'Disetujui', 'Ditolak']:
        sql += ' AND c.status_penerimaan = %s'
        params.append(status_filter)

    sql += ' ORDER BY c.timestamp DESC'
    rows = execute_raw_sql(sql, params)
    claims = [build_claim_item(row) for row in rows]

    context = {
        'member': member,
        'claims': claims,
        'status_filter': status_filter,
        'status_choices': ['Semua', 'Menunggu', 'Disetujui', 'Ditolak'],
    }
    return render(request, 'claim/claim_list.html', context)


@login_required_member
def claim_create(request):
    member = get_member(request)
    maskapais = get_maskapai_list()
    bandaras = get_bandara_list()
    kelas_choices = ClaimMissingMiles.KELAS_CHOICES

    if request.method == 'POST':
        maskapai_kode = request.POST.get('maskapai')
        bandara_asal_kode = request.POST.get('bandara_asal')
        bandara_tujuan_kode = request.POST.get('bandara_tujuan')
        tanggal_penerbangan = request.POST.get('tanggal_penerbangan')
        flight_number = request.POST.get('flight_number', '').strip().upper()
        nomor_tiket = request.POST.get('nomor_tiket', '').strip()
        kelas_kabin = request.POST.get('kelas_kabin')
        pnr = request.POST.get('pnr', '').strip().upper()

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

        if not get_maskapai_by_pk(maskapai_kode):
            messages.error(request, 'Maskapai tidak valid.')
        elif not get_bandara_by_pk(bandara_asal_kode) or not get_bandara_by_pk(bandara_tujuan_kode):
            messages.error(request, 'Bandara tidak valid.')
        else:
            try:
                sql = """
                    INSERT INTO claim_missing_miles
                        (email_member, maskapai, bandara_asal, bandara_tujuan,
                         tanggal_penerbangan, flight_number, nomor_tiket,
                         kelas_kabin, pnr, status_penerimaan, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                execute_raw_sql_update(sql, [
                    member.email_id,
                    maskapai_kode,
                    bandara_asal_kode,
                    bandara_tujuan_kode,
                    tanggal_penerbangan,
                    flight_number,
                    nomor_tiket,
                    kelas_kabin,
                    pnr,
                    'Menunggu',
                    timezone.now(),
                ])
                messages.success(request, 'Klaim berhasil diajukan dan sedang menunggu verifikasi.')
                return redirect('green:claim_list')
            except Exception as e:
                if 'unique' in str(e).lower():
                    messages.error(request, 'Klaim duplikat: kombinasi flight number, tanggal, dan nomor tiket sudah pernah diajukan.')
                else:
                    messages.error(request, 'Terjadi kesalahan database saat mengajukan klaim.')

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


@login_required_member
def claim_edit(request, pk):
    member = get_member(request)
    claim = get_claim_by_pk_and_member(pk, member.email_id)

    if not claim:
        messages.error(request, 'Klaim tidak ditemukan.')
        return redirect('green:claim_list')

    if claim.status_penerimaan != 'Menunggu':
        messages.error(request, 'Klaim yang sudah diproses tidak dapat diubah.')
        return redirect('green:claim_list')

    maskapais = get_maskapai_list()
    bandaras = get_bandara_list()
    kelas_choices = ClaimMissingMiles.KELAS_CHOICES
    claim = build_claim_item(claim)

    if request.method == 'POST':
        maskapai_kode = request.POST.get('maskapai')
        bandara_asal_kode = request.POST.get('bandara_asal')
        bandara_tujuan_kode = request.POST.get('bandara_tujuan')
        tanggal_penerbangan = request.POST.get('tanggal_penerbangan')
        flight_number = request.POST.get('flight_number', '').strip().upper()
        nomor_tiket = request.POST.get('nomor_tiket', '').strip()
        kelas_kabin = request.POST.get('kelas_kabin')
        pnr = request.POST.get('pnr', '').strip().upper()

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
            sql = """
                UPDATE claim_missing_miles
                SET maskapai = %s,
                    bandara_asal = %s,
                    bandara_tujuan = %s,
                    tanggal_penerbangan = %s,
                    flight_number = %s,
                    nomor_tiket = %s,
                    kelas_kabin = %s,
                    pnr = %s
                WHERE id = %s
            """
            execute_raw_sql_update(sql, [
                maskapai_kode,
                bandara_asal_kode,
                bandara_tujuan_kode,
                tanggal_penerbangan,
                flight_number,
                nomor_tiket,
                kelas_kabin,
                pnr,
                claim.id,
            ])
            messages.success(request, 'Klaim berhasil diperbarui.')
            return redirect('green:claim_list')
        except Exception as e:
            if 'unique' in str(e).lower():
                messages.error(request, 'Klaim duplikat: kombinasi flight number, tanggal, dan nomor tiket sudah pernah diajukan.')
            else:
                messages.error(request, 'Terjadi kesalahan database saat memperbarui klaim.')
            return render(request, 'claim/claim_form.html', {
                'member': member, 'claim': claim,
                'maskapais': maskapais, 'bandaras': bandaras,
                'kelas_choices': kelas_choices, 'is_edit': True,
            })

    return render(request, 'claim/claim_form.html', {
        'member': member,
        'claim': claim,
        'maskapais': maskapais,
        'bandaras': bandaras,
        'kelas_choices': kelas_choices,
        'is_edit': True,
    })


@login_required_member
def claim_delete(request, pk):
    member = get_member(request)
    claim = get_claim_by_pk_and_member(pk, member.email_id)

    if not claim:
        messages.error(request, 'Klaim tidak ditemukan.')
        return redirect('green:claim_list')

    if claim.status_penerimaan != 'Menunggu':
        messages.error(request, 'Klaim yang sudah diproses tidak dapat dibatalkan.')
        return redirect('green:claim_list')

    if request.method == 'POST':
        sql = 'DELETE FROM claim_missing_miles WHERE id = %s'
        execute_raw_sql_update(sql, [pk])
        messages.success(request, 'Klaim berhasil dibatalkan.')
        return redirect('green:claim_list')

    return render(request, 'claim/claim_confirm_delete.html', {
        'member': member,
        'claim': build_claim_item(claim),
    })


@login_required_staf
def staf_claim_list(request):
    staf = get_staf(request)
    status_filter = request.GET.get('status', 'Semua')
    maskapai_filter = request.GET.get('maskapai', '')
    tgl_dari = request.GET.get('tgl_dari', '')
    tgl_sampai = request.GET.get('tgl_sampai', '')

    sql = """
        SELECT c.id, c.email_member, c.maskapai, c.bandara_asal, c.bandara_tujuan,
               c.tanggal_penerbangan, c.flight_number, c.nomor_tiket,
               c.kelas_kabin, c.pnr, c.status_penerimaan, c.timestamp,
               m.nama_maskapai as maskapai_nama,
               ba.iata_code as bandara_asal_iata, ba.nama as bandara_asal_nama,
               ba.kota as bandara_asal_kota, ba.negara as bandara_asal_negara,
               bt.iata_code as bandara_tujuan_iata, bt.nama as bandara_tujuan_nama,
               bt.kota as bandara_tujuan_kota, bt.negara as bandara_tujuan_negara,
               pm.first_mid_name as member_first_name, pm.last_name as member_last_name
        FROM claim_missing_miles c
        JOIN maskapai m ON c.maskapai = m.kode_maskapai
        JOIN bandara ba ON c.bandara_asal = ba.iata_code
        JOIN bandara bt ON c.bandara_tujuan = bt.iata_code
        JOIN member mb ON c.email_member = mb.email
        JOIN pengguna pm ON mb.email = pm.email
        WHERE 1=1
    """
    params = []

    if status_filter in ['Menunggu', 'Disetujui', 'Ditolak']:
        sql += ' AND c.status_penerimaan = %s'
        params.append(status_filter)

    if maskapai_filter:
        sql += ' AND c.maskapai = %s'
        params.append(maskapai_filter)

    if tgl_dari:
        sql += ' AND DATE(c.timestamp) >= %s'
        params.append(tgl_dari)

    if tgl_sampai:
        sql += ' AND DATE(c.timestamp) <= %s'
        params.append(tgl_sampai)

    sql += ' ORDER BY c.timestamp DESC'
    rows = execute_raw_sql(sql, params)
    claims = [build_claim_item(row) for row in rows]

    maskapais = get_maskapai_list()

    context = {
        'staf': staf,
        'claims': claims,
        'maskapais': maskapais,
        'status_filter': status_filter,
        'maskapai_filter': maskapai_filter,
        'tgl_dari': tgl_dari,
        'tgl_sampai': tgl_sampai,
        'status_choices': ['Semua', 'Menunggu', 'Disetujui', 'Ditolak'],
    }
    return render(request, 'claim/staf_claim_list.html', context)


@login_required_staf
def staf_claim_proses(request, pk):
    staf = get_staf(request)
    claim = get_claim_by_pk(pk)

    if not claim:
        messages.error(request, 'Klaim tidak ditemukan.')
        return redirect('green:staf_claim_list')

    if claim.status_penerimaan != 'Menunggu':
        messages.error(request, 'Klaim ini sudah diproses sebelumnya.')
        return redirect('green:staf_claim_list')

    claim = build_claim_item(claim)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action not in ['Disetujui', 'Ditolak']:
            messages.error(request, 'Aksi tidak valid.')
            return redirect('green:staf_claim_list')

        try:
            member = get_member_by_email(claim.email_member)
            if not member:
                messages.error(request, 'Member tidak ditemukan.')
                return redirect('green:staf_claim_list')

            commands = [
                ('UPDATE claim_missing_miles SET status_penerimaan = %s, email_staf = %s WHERE id = %s',
                 [action, staf.email_id, claim.id]),
            ]

            if action == 'Disetujui':
                miles = ClaimMissingMiles.MILES_PER_KELAS.get(claim.kelas_kabin, 500)
                commands.extend([
                    ('UPDATE member SET award_miles = award_miles + %s WHERE email = %s', [miles, member.email]),
                    ('UPDATE member SET total_miles = total_miles + %s WHERE email = %s', [miles, member.email]),
                ])

            execute_raw_sql_many(commands)

            if action == 'Disetujui':
                messages.success(request, f'Klaim disetujui. {miles} miles ditambahkan ke akun {member.email_id}.')
            else:
                messages.success(request, 'Klaim telah ditolak.')
            return redirect('green:staf_claim_list')
        except Exception as e:
            messages.error(request, 'Terjadi kesalahan saat memproses klaim.')
            print(e)
            return redirect('green:staf_claim_list')

    return render(request, 'claim/staf_claim_proses.html', {
        'staf': staf,
        'claim': claim,
    })


@login_required_member
def transfer_list(request):
    member = get_member(request)
    if not member:
        messages.error(request, 'Silakan login sebagai Member terlebih dahulu.')
        return redirect('main:login')

    sql_out = """
        SELECT t.timestamp, t.jumlah, t.catatan,
               'Kirim' AS tipe,
               p.first_mid_name || ' ' || p.last_name AS member_nama,
               m.email AS member_email
        FROM transfer t
        JOIN member m ON t.email_member_2 = m.email
        JOIN pengguna p ON m.email = p.email
        WHERE t.email_member_1 = %s
    """
    sql_in = """
        SELECT t.timestamp, t.jumlah, t.catatan,
               'Terima' AS tipe,
               p.first_mid_name || ' ' || p.last_name AS member_nama,
               m.email AS member_email
        FROM transfer t
        JOIN member m ON t.email_member_1 = m.email
        JOIN pengguna p ON m.email = p.email
        WHERE t.email_member_2 = %s
    """

    if not settings.PRODUCTION:
        sql_out = sql_out.replace("|| ' ' ||", "|| ' ' ||")
        sql_in = sql_in.replace("|| ' ' ||", "|| ' ' ||")

    outgoing = execute_raw_sql(sql_out, [member.email_id])
    incoming = execute_raw_sql(sql_in, [member.email_id])
    riwayat = sorted(outgoing + incoming, key=lambda x: x.timestamp, reverse=True)

    return render(request, 'transfer/transfer_list.html', {
        'member': member,
        'riwayat': riwayat,
    })


@login_required_member
def transfer_create(request):
    member = get_member(request)
    if not member:
        messages.error(request, 'Silakan login sebagai Member terlebih dahulu.')
        return redirect('main:login')

    if request.method == 'POST':
        email_penerima = request.POST.get('email_penerima', '').strip()
        jumlah_str = request.POST.get('jumlah', '').strip()
        catatan = request.POST.get('catatan', '').strip()

        if not email_penerima or not jumlah_str:
            messages.error(request, 'Email penerima dan jumlah miles wajib diisi.')
            return render(request, 'transfer/transfer_form.html', {'member': member})

        if email_penerima == member.email_id:
            messages.error(request, 'Anda tidak dapat mentransfer miles ke diri sendiri.')
            return render(request, 'transfer/transfer_form.html', {'member': member})

        try:
            jumlah = int(jumlah_str)
            if jumlah <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Jumlah miles harus berupa angka positif.')
            return render(request, 'transfer/transfer_form.html', {'member': member})

        penerima = get_member_by_email(email_penerima)
        if not penerima:
            messages.error(request, 'Email penerima tidak terdaftar sebagai Member aktif.')
            return render(request, 'transfer/transfer_form.html', {'member': member})

        if member.award_miles < jumlah:
            messages.error(request, f'Award miles Anda tidak mencukupi. Tersedia: {member.award_miles} miles.')
            return render(request, 'transfer/transfer_form.html', {'member': member})

        try:
            commands = [
                ('INSERT INTO transfer (email_member_1, email_member_2, timestamp, jumlah, catatan) VALUES (%s, %s, %s, %s, %s)',
                 [member.email_id, email_penerima, timezone.now(), jumlah, catatan or None]),
                ('UPDATE member SET award_miles = award_miles - %s WHERE email = %s', [jumlah, member.email_id]),
                ('UPDATE member SET award_miles = award_miles + %s WHERE email = %s', [jumlah, email_penerima]),
            ]
            execute_raw_sql_many(commands)
            messages.success(request, f'{jumlah} miles berhasil ditransfer ke {email_penerima}.')
            return redirect('green:transfer_list')
        except Exception as e:
            messages.error(request, 'Terjadi kesalahan saat melakukan transfer miles.')
            print(e)
            return render(request, 'transfer/transfer_form.html', {'member': member})

    return render(request, 'transfer/transfer_form.html', {'member': member})