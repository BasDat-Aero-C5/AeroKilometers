from datetime import date, datetime
import os
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import RealDictCursor
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods


class DBRow(dict):
    def __getattr__(self, name):
        if name in self:
            return self[name]
        if name == 'pk' and 'id' in self:
            return self['id']
        if name == 'email_id' and 'email' in self:
            return self['email']
        raise AttributeError(f"Attribute {name} not found")

    def __setattr__(self, name, value):
        self[name] = value


def get_db_connection():
    if settings.PRODUCTION:
        db_url = os.environ.get('DATABASE_URL')
        parsed = urlparse(db_url)
        return psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            sslmode='require',
        )

    from django.db import connection
    return connection


def execute_raw_sql(sql, params=None):
    try:
        conn = get_db_connection()
        is_postgres = isinstance(conn, psycopg2.extensions.connection)
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_postgres else conn.cursor()
        cursor.execute(sql, params or [])

        if not cursor.description:
            rows = []
        elif is_postgres:
            rows = [DBRow(row) for row in cursor.fetchall()]
        else:
            columns = [col[0] for col in cursor.description]
            rows = [DBRow(dict(zip(columns, row))) for row in cursor.fetchall()]

        cursor.close()
        if is_postgres:
            conn.close()
        return rows
    except Exception as e:
        print(f"Database error: {e}")
        return []


def execute_raw_sql_update(sql, params=None):
    conn = get_db_connection()
    is_postgres = isinstance(conn, psycopg2.extensions.connection)
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params or [])
        rowcount = cursor.rowcount
        conn.commit()
        return rowcount
    finally:
        cursor.close()
        if is_postgres:
            conn.close()


def execute_transaction(commands):
    conn = get_db_connection()
    is_postgres = isinstance(conn, psycopg2.extensions.connection)
    cursor = conn.cursor()
    try:
        for sql, params in commands:
            cursor.execute(sql, params or [])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        if is_postgres:
            conn.close()


def get_staf(request):
    email = request.session.get('email')
    role = request.session.get('role')

    if not email or role != 'staff':
        return None

    sql = """
        SELECT s.email, s.id_staf, s.kode_maskapai,
               m.nama_maskapai,
               p.first_mid_name, p.last_name, p.salutation,
               p.country_code, p.mobile_number,
               p.tanggal_lahir, p.kewarganegaraan,
               s.email AS email_id
        FROM staf s
        JOIN pengguna p ON s.email = p.email
        JOIN maskapai m ON s.kode_maskapai = m.kode_maskapai
        WHERE s.email = %s
    """
    rows = execute_raw_sql(sql, [email])
    return rows[0] if rows else None


def login_required_staff(view_func):
    def wrapper(request, *args, **kwargs):
        if not get_staf(request):
            messages.error(request, 'Silakan login sebagai Staff terlebih dahulu.')
            return redirect('main:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def format_date_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    return str(value or '')[:10]


def provider_name(row):
    return row.get('nama_mitra') or row.get('nama_maskapai') or f"Penyedia {row.get('id_penyedia')}"


def get_provider_options():
    sql = """
        SELECT p.id AS id_penyedia, mt.nama_mitra, mk.nama_maskapai
        FROM penyedia p
        LEFT JOIN mitra mt ON mt.id_penyedia = p.id
        LEFT JOIN maskapai mk ON mk.id_penyedia = p.id
        ORDER BY p.id
    """
    providers = execute_raw_sql(sql)
    for provider in providers:
        provider['id'] = provider['id_penyedia']
        provider['nama_penyedia'] = provider_name(provider)
    return providers


def get_hadiah(kode_hadiah):
    rows = execute_raw_sql(
        """
        SELECT h.kode_hadiah, h.nama AS nama_hadiah, h.nama,
               h.miles AS harga_miles, h.miles, h.deskripsi,
               h.valid_start_date, h.program_end, h.id_penyedia,
               (h.valid_start_date <= CURRENT_DATE AND h.program_end >= CURRENT_DATE) AS is_active,
               mt.nama_mitra, mk.nama_maskapai
        FROM hadiah h
        LEFT JOIN mitra mt ON mt.id_penyedia = h.id_penyedia
        LEFT JOIN maskapai mk ON mk.id_penyedia = h.id_penyedia
        WHERE h.kode_hadiah = %s
        """,
        [kode_hadiah],
    )
    if not rows:
        return None

    hadiah = rows[0]
    hadiah['penyedia_nama'] = provider_name(hadiah)
    hadiah['valid_start_date_value'] = format_date_value(hadiah.get('valid_start_date'))
    hadiah['program_end_value'] = format_date_value(hadiah.get('program_end'))
    return hadiah


def get_mitra(email_mitra):
    rows = execute_raw_sql(
        """
        SELECT email_mitra, id_penyedia, id_penyedia AS id_penyedia_id,
               nama_mitra, tanggal_kerja_sama
        FROM mitra
        WHERE email_mitra = %s
        """,
        [email_mitra],
    )
    if not rows:
        return None

    mitra = rows[0]
    mitra['tanggal_kerja_sama_value'] = format_date_value(mitra.get('tanggal_kerja_sama'))
    return mitra


@login_required_staff
def daftar_hadiah(request):
    staf = get_staf(request)
    penyedia_filter = request.GET.get('penyedia', '')
    status_filter = request.GET.get('status', '')

    sql = """
        SELECT h.kode_hadiah, h.nama AS nama_hadiah, h.nama,
               h.miles AS harga_miles, h.miles, h.deskripsi,
               h.valid_start_date, h.program_end, h.id_penyedia,
               (h.valid_start_date <= CURRENT_DATE AND h.program_end >= CURRENT_DATE) AS is_active,
               mt.nama_mitra, mk.nama_maskapai
        FROM hadiah h
        LEFT JOIN mitra mt ON mt.id_penyedia = h.id_penyedia
        LEFT JOIN maskapai mk ON mk.id_penyedia = h.id_penyedia
        WHERE 1 = 1
    """
    params = []

    if penyedia_filter:
        sql += " AND h.id_penyedia = %s"
        params.append(penyedia_filter)

    if status_filter == 'aktif':
        sql += " AND h.valid_start_date <= CURRENT_DATE AND h.program_end >= CURRENT_DATE"
    elif status_filter == 'tidak_aktif':
        sql += " AND NOT (h.valid_start_date <= CURRENT_DATE AND h.program_end >= CURRENT_DATE)"

    sql += " ORDER BY h.valid_start_date DESC"

    hadiah_list = execute_raw_sql(sql, params)
    for hadiah in hadiah_list:
        hadiah['penyedia_nama'] = provider_name(hadiah)
        hadiah['is_active'] = bool(hadiah.get('is_active'))

    context = {
        'staf': staf,
        'hadiah_list': hadiah_list,
        'rewards': hadiah_list,
        'penyedia_list': get_provider_options(),
        'penyedia_filter': penyedia_filter,
        'status_filter': status_filter,
        'navbar_type': 'staff',
    }
    return render(request, 'hadiah/daftar_hadiah.html', context)


@login_required_staff
@require_http_methods(["GET", "POST"])
def tambah_hadiah(request):
    staf = get_staf(request)

    if request.method == 'POST':
        nama_hadiah = request.POST.get('nama_hadiah', '').strip()
        harga_miles = request.POST.get('harga_miles', '').strip()
        deskripsi = request.POST.get('deskripsi', '').strip()
        id_penyedia = request.POST.get('id_penyedia', '').strip()
        valid_start_date = (
            request.POST.get('valid_start_date', '').strip()
            or request.POST.get('tanggal_mulai', '').strip()
        )
        program_end = (
            request.POST.get('program_end', '').strip()
            or request.POST.get('tanggal_berakhir', '').strip()
        )

        if not all([nama_hadiah, harga_miles, deskripsi, id_penyedia, valid_start_date, program_end]):
            messages.error(request, 'Semua field wajib diisi.')
        else:
            try:
                harga_miles_int = int(harga_miles)
                if harga_miles_int <= 0:
                    raise ValueError

                kode_hadiah = f"RWD-{int(timezone.now().timestamp()) % 1000000:06d}"
                execute_raw_sql_update(
                    """
                    INSERT INTO hadiah
                        (kode_hadiah, nama, miles, deskripsi, valid_start_date, program_end, id_penyedia)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    [kode_hadiah, nama_hadiah, harga_miles_int, deskripsi, valid_start_date, program_end, id_penyedia],
                )
                messages.success(request, f'Hadiah {nama_hadiah} berhasil ditambahkan dengan kode {kode_hadiah}.')
                return redirect('red:daftar_hadiah')
            except ValueError:
                messages.error(request, 'Harga miles harus berupa angka positif.')
            except Exception as e:
                messages.error(request, f'Terjadi kesalahan: {str(e)}')

    return render(request, 'hadiah/tambah_hadiah.html', {
        'staf': staf,
        'providers': get_provider_options(),
        'penyedia_list': get_provider_options(),
        'navbar_type': 'staff',
    })


@login_required_staff
@require_http_methods(["GET", "POST"])
def edit_hadiah(request, kode_hadiah):
    staf = get_staf(request)
    hadiah = get_hadiah(kode_hadiah)

    if not hadiah:
        messages.error(request, 'Hadiah tidak ditemukan.')
        return redirect('red:daftar_hadiah')

    if request.method == 'POST':
        nama_hadiah = request.POST.get('nama_hadiah', '').strip()
        harga_miles = request.POST.get('harga_miles', '').strip()
        deskripsi = request.POST.get('deskripsi', '').strip()
        id_penyedia = request.POST.get('id_penyedia', '').strip()
        valid_start_date = request.POST.get('valid_start_date', '').strip()
        program_end = request.POST.get('program_end', '').strip()

        if not all([nama_hadiah, harga_miles, deskripsi, id_penyedia, valid_start_date, program_end]):
            messages.error(request, 'Semua field wajib diisi.')
        else:
            try:
                harga_miles_int = int(harga_miles)
                if harga_miles_int <= 0:
                    raise ValueError

                execute_raw_sql_update(
                    """
                    UPDATE hadiah
                    SET nama = %s, miles = %s, deskripsi = %s,
                        valid_start_date = %s, program_end = %s, id_penyedia = %s
                    WHERE kode_hadiah = %s
                    """,
                    [nama_hadiah, harga_miles_int, deskripsi, valid_start_date, program_end, id_penyedia, kode_hadiah],
                )
                messages.success(request, f'Hadiah {nama_hadiah} berhasil diperbarui.')
                return redirect('red:daftar_hadiah')
            except ValueError:
                messages.error(request, 'Harga miles harus berupa angka positif.')
            except Exception as e:
                messages.error(request, f'Terjadi kesalahan: {str(e)}')

    return render(request, 'hadiah/edit_hadiah.html', {
        'staf': staf,
        'hadiah': hadiah,
        'providers': get_provider_options(),
        'penyedia_list': get_provider_options(),
        'navbar_type': 'staff',
    })


@login_required_staff
@require_http_methods(["GET", "POST"])
def hapus_hadiah(request, kode_hadiah):
    hadiah = get_hadiah(kode_hadiah)

    if not hadiah:
        messages.error(request, 'Hadiah tidak ditemukan.')
        return redirect('red:daftar_hadiah')

    if request.method == 'POST':
        try:
            execute_raw_sql_update("DELETE FROM hadiah WHERE kode_hadiah = %s", [kode_hadiah])
            messages.success(request, 'Hadiah berhasil dihapus.')
            return redirect('red:daftar_hadiah')
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')

    return render(request, 'hadiah/hapus_hadiah.html', {
        'hadiah': hadiah,
        'navbar_type': 'staff',
    })


@login_required_staff
def daftar_mitra(request):
    staf = get_staf(request)
    mitra_list = execute_raw_sql(
        """
        SELECT email_mitra, id_penyedia, id_penyedia AS id_penyedia_id,
               nama_mitra, tanggal_kerja_sama
        FROM mitra
        ORDER BY tanggal_kerja_sama DESC
        """
    )

    context = {
        'staf': staf,
        'mitra_list': mitra_list,
        'mitras': mitra_list,
        'navbar_type': 'staff',
    }
    return render(request, 'mitra/daftar_mitra.html', context)


def create_mitra(nama_mitra, email_mitra, tanggal_kerja_sama):
    conn = get_db_connection()
    is_postgres = isinstance(conn, psycopg2.extensions.connection)
    cursor = conn.cursor()
    try:
        if is_postgres:
            cursor.execute("INSERT INTO penyedia DEFAULT VALUES RETURNING id")
            id_penyedia = cursor.fetchone()[0]
        else:
            cursor.execute("INSERT INTO penyedia DEFAULT VALUES")
            id_penyedia = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO mitra (email_mitra, id_penyedia, nama_mitra, tanggal_kerja_sama)
            VALUES (%s, %s, %s, %s)
            """,
            [email_mitra, id_penyedia, nama_mitra, tanggal_kerja_sama],
        )
        conn.commit()
        return id_penyedia
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        if is_postgres:
            conn.close()


@login_required_staff
@require_http_methods(["GET", "POST"])
def tambah_mitra(request):
    staf = get_staf(request)

    if request.method == 'POST':
        nama_mitra = request.POST.get('nama_mitra', '').strip()
        email_mitra = request.POST.get('email_mitra', '').strip()
        tanggal_kerja_sama = request.POST.get('tanggal_kerja_sama', '').strip()

        if not all([nama_mitra, email_mitra, tanggal_kerja_sama]):
            messages.error(request, 'Semua field wajib diisi.')
        elif '@' not in email_mitra:
            messages.error(request, 'Format email tidak valid.')
        else:
            try:
                create_mitra(nama_mitra, email_mitra, tanggal_kerja_sama)
                messages.success(request, f'Mitra {nama_mitra} berhasil ditambahkan.')
                return redirect('red:daftar_mitra')
            except Exception as e:
                messages.error(request, f'Terjadi kesalahan: {str(e)}')

    return render(request, 'mitra/tambah_mitra.html', {
        'staf': staf,
        'navbar_type': 'staff',
    })


@login_required_staff
@require_http_methods(["GET", "POST"])
def edit_mitra(request, email_mitra):
    staf = get_staf(request)
    mitra = get_mitra(email_mitra)

    if not mitra:
        messages.error(request, 'Mitra tidak ditemukan.')
        return redirect('red:daftar_mitra')

    if request.method == 'POST':
        nama_mitra = request.POST.get('nama_mitra', '').strip()
        tanggal_kerja_sama = request.POST.get('tanggal_kerja_sama', '').strip()

        if not all([nama_mitra, tanggal_kerja_sama]):
            messages.error(request, 'Semua field wajib diisi.')
        else:
            try:
                execute_raw_sql_update(
                    """
                    UPDATE mitra
                    SET nama_mitra = %s, tanggal_kerja_sama = %s
                    WHERE email_mitra = %s
                    """,
                    [nama_mitra, tanggal_kerja_sama, email_mitra],
                )
                messages.success(request, f'Mitra {nama_mitra} berhasil diperbarui.')
                return redirect('red:daftar_mitra')
            except Exception as e:
                messages.error(request, f'Terjadi kesalahan: {str(e)}')

    return render(request, 'mitra/edit_mitra.html', {
        'staf': staf,
        'mitra': mitra,
        'navbar_type': 'staff',
    })


@login_required_staff
@require_http_methods(["GET", "POST"])
def hapus_mitra(request, email_mitra):
    mitra = get_mitra(email_mitra)

    if not mitra:
        messages.error(request, 'Mitra tidak ditemukan.')
        return redirect('red:daftar_mitra')

    if request.method == 'POST':
        try:
            id_penyedia = mitra.id_penyedia
            execute_transaction([
                ("DELETE FROM hadiah WHERE id_penyedia = %s", [id_penyedia]),
                ("DELETE FROM mitra WHERE email_mitra = %s", [email_mitra]),
                ("DELETE FROM penyedia WHERE id = %s", [id_penyedia]),
            ])
            messages.success(request, 'Mitra berhasil dihapus.')
            return redirect('red:daftar_mitra')
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')

    return render(request, 'mitra/hapus_mitra.html', {
        'mitra': mitra,
        'navbar_type': 'staff',
    })
