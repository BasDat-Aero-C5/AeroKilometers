from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.conf import settings
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from urllib.parse import urlparse

from modules.green.models import Staf, Member


# Database connection helper
def get_db_connection():
    """Get psycopg2 database connection."""
    if settings.PRODUCTION:
        db_url = os.environ.get('DATABASE_URL')
        parsed = urlparse(db_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            sslmode='require'
        )
    else:
        from django.db import connection
        return connection
    return conn


def execute_raw_sql(sql, params=None):
    """Execute raw SQL query and return results."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if isinstance(conn, psycopg2.extensions.connection) else conn.cursor()
        
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        
        if cursor.description:
            if isinstance(conn, psycopg2.extensions.connection):
                results = cursor.fetchall()
                result_list = [dict(row) for row in results]
            else:
                columns = [col[0] for col in cursor.description]
                results = cursor.fetchall()
                result_list = [dict(zip(columns, row)) for row in results]
        else:
            result_list = []
        
        cursor.close()
        if hasattr(conn, 'commit'):
            conn.commit()
        if isinstance(conn, psycopg2.extensions.connection):
            conn.close()
        
        return result_list
    except Exception as e:
        print(f"Database error: {e}")
        return []


def execute_raw_sql_update(sql, params=None):
    """Execute raw SQL update/insert/delete query."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        
        rowcount = cursor.rowcount
        cursor.close()
        conn.commit()
        if isinstance(conn, psycopg2.extensions.connection):
            conn.close()
        
        return rowcount
    except Exception as e:
        print(f"Database error: {e}")
        return 0


# Authentication Helpers
def get_staf(request):
    """Return Staf object for the logged-in user, or None."""
    email = request.session.get('email')
    role = request.session.get('role')
    
    if not email or role != 'staff':
        return None
    try:
        return Staf.objects.select_related('email', 'kode_maskapai').get(email=email)
    except Staf.DoesNotExist:
        return None


def login_required_staff(view_func):
    """Decorator: redirect to login if not Staff."""
    def wrapper(request, *args, **kwargs):
        if not get_staf(request):
            messages.error(request, 'Silakan login sebagai Staff terlebih dahulu.')
            return redirect('main:login')
        return view_func(request, *args, **kwargs)
    return wrapper


# ===== REWARDS MANAGEMENT (Hadiah) =====

@login_required_staff
def daftar_hadiah(request):
    """R — Display list of all rewards."""
    staf = get_staf(request)
    
    sql = """
        SELECT 
            kode_hadiah,
            nama_hadiah,
            harga_miles,
            deskripsi,
            tanggal_mulai,
            tanggal_berakhir,
            id_penyedia
        FROM HADIAH
        ORDER BY tanggal_mulai DESC
    """
    
    rewards = execute_raw_sql(sql)
    
    context = {
        'staf': staf,
        'rewards': rewards,
        'navbar_type': 'staff',
    }
    return render(request, 'hadiah/daftar_hadiah.html', context)


@login_required_staff
@require_http_methods(["GET", "POST"])
def tambah_hadiah(request):
    """C — Create new reward."""
    staf = get_staf(request)
    
    if request.method == 'POST':
        nama_hadiah = request.POST.get('nama_hadiah', '').strip()
        harga_miles = request.POST.get('harga_miles', '').strip()
        deskripsi = request.POST.get('deskripsi', '').strip()
        id_penyedia = request.POST.get('id_penyedia', '').strip()
        tanggal_mulai = request.POST.get('tanggal_mulai', '').strip()
        tanggal_berakhir = request.POST.get('tanggal_berakhir', '').strip()
        
        if not all([nama_hadiah, harga_miles, deskripsi, id_penyedia, tanggal_mulai, tanggal_berakhir]):
            messages.error(request, 'Semua field wajib diisi.')
            return render(request, 'hadiah/tambah_hadiah.html', {'navbar_type': 'staff', 'staf': staf})
        
        try:
            harga_miles = int(harga_miles)
            if harga_miles <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Harga miles harus berupa angka positif.')
            return render(request, 'hadiah/tambah_hadiah.html', {'navbar_type': 'staff', 'staf': staf})
        
        try:
            kode_hadiah = f"RWD-{int(timezone.now().timestamp()) % 10000:04d}"
            
            sql = """
                INSERT INTO HADIAH 
                (kode_hadiah, nama_hadiah, harga_miles, deskripsi, id_penyedia, tanggal_mulai, tanggal_berakhir)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            execute_raw_sql_update(sql, [
                kode_hadiah, nama_hadiah, harga_miles, deskripsi, 
                id_penyedia, tanggal_mulai, tanggal_berakhir
            ])
            
            messages.success(request, f'Hadiah {nama_hadiah} berhasil ditambahkan dengan kode {kode_hadiah}.')
            return redirect('red:daftar_hadiah')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
            return render(request, 'hadiah/tambah_hadiah.html', {'navbar_type': 'staff', 'staf': staf})
    
    sql_providers = "SELECT id_penyedia, nama_penyedia FROM PENYEDIA ORDER BY nama_penyedia"
    providers = execute_raw_sql(sql_providers)
    
    context = {
        'staf': staf,
        'providers': providers,
        'navbar_type': 'staff',
    }
    return render(request, 'hadiah/tambah_hadiah.html', context)


@login_required_staff
@require_http_methods(["GET", "POST"])
def edit_hadiah(request):
    """U — Update existing reward."""
    staf = get_staf(request)
    kode_hadiah = request.GET.get('kode') or request.POST.get('kode_hadiah')
    
    sql = "SELECT * FROM HADIAH WHERE kode_hadiah = %s"
    rewards = execute_raw_sql(sql, [kode_hadiah])
    
    if not rewards:
        messages.error(request, 'Hadiah tidak ditemukan.')
        return redirect('red:daftar_hadiah')
    
    hadiah = rewards[0]
    
    if request.method == 'POST':
        nama_hadiah = request.POST.get('nama_hadiah', '').strip()
        harga_miles = request.POST.get('harga_miles', '').strip()
        deskripsi = request.POST.get('deskripsi', '').strip()
        id_penyedia = request.POST.get('id_penyedia', '').strip()
        tanggal_berakhir = request.POST.get('tanggal_berakhir', '').strip()
        
        if not all([nama_hadiah, harga_miles, deskripsi, id_penyedia, tanggal_berakhir]):
            messages.error(request, 'Semua field wajib diisi.')
            context = {'staf': staf, 'hadiah': hadiah, 'navbar_type': 'staff'}
            return render(request, 'hadiah/edit_hadiah.html', context)
        
        try:
            harga_miles = int(harga_miles)
            if harga_miles <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Harga miles harus berupa angka positif.')
            context = {'staf': staf, 'hadiah': hadiah, 'navbar_type': 'staff'}
            return render(request, 'hadiah/edit_hadiah.html', context)
        
        try:
            sql = """
                UPDATE HADIAH
                SET nama_hadiah = %s, harga_miles = %s, deskripsi = %s, 
                    id_penyedia = %s, tanggal_berakhir = %s
                WHERE kode_hadiah = %s
            """
            
            execute_raw_sql_update(sql, [
                nama_hadiah, harga_miles, deskripsi, id_penyedia, tanggal_berakhir, kode_hadiah
            ])
            
            messages.success(request, f'Hadiah {nama_hadiah} berhasil diperbarui.')
            return redirect('red:daftar_hadiah')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    sql_providers = "SELECT id_penyedia, nama_penyedia FROM PENYEDIA ORDER BY nama_penyedia"
    providers = execute_raw_sql(sql_providers)
    
    context = {
        'staf': staf,
        'hadiah': hadiah,
        'providers': providers,
        'navbar_type': 'staff',
    }
    return render(request, 'hadiah/edit_hadiah.html', context)


@login_required_staff
@require_http_methods(["POST"])
def hapus_hadiah(request):
    """D — Delete reward."""
    staf = get_staf(request)
    kode_hadiah = request.POST.get('kode_hadiah', '').strip()
    
    if not kode_hadiah:
        messages.error(request, 'Kode hadiah tidak valid.')
        return redirect('red:daftar_hadiah')
    
    try:
        sql = "DELETE FROM HADIAH WHERE kode_hadiah = %s"
        execute_raw_sql_update(sql, [kode_hadiah])
        messages.success(request, 'Hadiah berhasil dihapus.')
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return redirect('red:daftar_hadiah')


# ===== PARTNER MANAGEMENT (Mitra) =====

@login_required_staff
def daftar_mitra(request):
    """R — Display list of all partners."""
    staf = get_staf(request)
    
    sql = """
        SELECT 
            id_penyedia,
            nama_penyedia,
            email_penyedia,
            tanggal_kerja_sama
        FROM PENYEDIA
        ORDER BY tanggal_kerja_sama DESC
    """
    
    mitras = execute_raw_sql(sql)
    
    context = {
        'staf': staf,
        'mitras': mitras,
        'navbar_type': 'staff',
    }
    return render(request, 'mitra/daftar_mitra.html', context)


@login_required_staff
@require_http_methods(["GET", "POST"])
def tambah_mitra(request):
    """C — Create new partner."""
    staf = get_staf(request)
    
    if request.method == 'POST':
        nama_penyedia = request.POST.get('nama_penyedia', '').strip()
        email_penyedia = request.POST.get('email_penyedia', '').strip()
        tanggal_kerja_sama = request.POST.get('tanggal_kerja_sama', '').strip()
        
        if not all([nama_penyedia, email_penyedia, tanggal_kerja_sama]):
            messages.error(request, 'Semua field wajib diisi.')
            return render(request, 'mitra/tambah_mitra.html', {'navbar_type': 'staff', 'staf': staf})
        
        if '@' not in email_penyedia:
            messages.error(request, 'Format email tidak valid.')
            return render(request, 'mitra/tambah_mitra.html', {'navbar_type': 'staff', 'staf': staf})
        
        try:
            sql = """
                INSERT INTO PENYEDIA 
                (nama_penyedia, email_penyedia, tanggal_kerja_sama)
                VALUES (%s, %s, %s)
            """
            
            execute_raw_sql_update(sql, [nama_penyedia, email_penyedia, tanggal_kerja_sama])
            
            messages.success(request, f'Mitra {nama_penyedia} berhasil ditambahkan.')
            return redirect('red:daftar_mitra')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
            return render(request, 'mitra/tambah_mitra.html', {'navbar_type': 'staff', 'staf': staf})
    
    context = {
        'staf': staf,
        'navbar_type': 'staff',
    }
    return render(request, 'mitra/tambah_mitra.html', context)


@login_required_staff
@require_http_methods(["GET", "POST"])
def edit_mitra(request):
    """U — Update existing partner."""
    staf = get_staf(request)
    id_penyedia = request.GET.get('id') or request.POST.get('id_penyedia')
    
    sql = "SELECT * FROM PENYEDIA WHERE id_penyedia = %s"
    mitras = execute_raw_sql(sql, [id_penyedia])
    
    if not mitras:
        messages.error(request, 'Mitra tidak ditemukan.')
        return redirect('red:daftar_mitra')
    
    mitra = mitras[0]
    
    if request.method == 'POST':
        nama_penyedia = request.POST.get('nama_penyedia', '').strip()
        tanggal_kerja_sama = request.POST.get('tanggal_kerja_sama', '').strip()
        
        if not all([nama_penyedia, tanggal_kerja_sama]):
            messages.error(request, 'Semua field wajib diisi.')
            context = {'staf': staf, 'mitra': mitra, 'navbar_type': 'staff'}
            return render(request, 'mitra/edit_mitra.html', context)
        
        try:
            sql = """
                UPDATE PENYEDIA
                SET nama_penyedia = %s, tanggal_kerja_sama = %s
                WHERE id_penyedia = %s
            """
            
            execute_raw_sql_update(sql, [nama_penyedia, tanggal_kerja_sama, id_penyedia])
            
            messages.success(request, f'Mitra {nama_penyedia} berhasil diperbarui.')
            return redirect('red:daftar_mitra')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    context = {
        'staf': staf,
        'mitra': mitra,
        'navbar_type': 'staff',
    }
    return render(request, 'mitra/edit_mitra.html', context)


@login_required_staff
@require_http_methods(["POST"])
def hapus_mitra(request):
    """D — Delete partner."""
    staf = get_staf(request)
    id_penyedia = request.POST.get('id_penyedia', '').strip()
    
    if not id_penyedia:
        messages.error(request, 'ID Mitra tidak valid.')
        return redirect('red:daftar_mitra')
    
    try:
        sql = "DELETE FROM PENYEDIA WHERE id_penyedia = %s"
        execute_raw_sql_update(sql, [id_penyedia])
        messages.success(request, 'Mitra berhasil dihapus.')
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return redirect('red:daftar_mitra')


# ===== REWARDS MANAGEMENT (Hadiah) =====

@login_required_staff
def daftar_hadiah(request):
    """R — Display list of all rewards."""
    staf = get_staf(request)
    
    # Fetch rewards using raw SQL
    sql = """
        SELECT 
            kode_hadiah,
            nama_hadiah,
            harga_miles,
            deskripsi,
            tanggal_mulai,
            tanggal_berakhir,
            id_penyedia
        FROM HADIAH
        ORDER BY tanggal_mulai DESC
    """
    
    rewards = execute_raw_sql(sql)
    
    context = {
        'staf': staf,
        'rewards': rewards,
        'navbar_type': 'staff',
    }
    return render(request, 'hadiah/daftar_hadiah.html', context)


@login_required_staff
@require_http_methods(["GET", "POST"])
def tambah_hadiah(request):
    """C — Create new reward."""
    staf = get_staf(request)
    
    if request.method == 'POST':
        nama_hadiah = request.POST.get('nama_hadiah', '').strip()
        harga_miles = request.POST.get('harga_miles', '').strip()
        deskripsi = request.POST.get('deskripsi', '').strip()
        id_penyedia = request.POST.get('id_penyedia', '').strip()
        tanggal_mulai = request.POST.get('tanggal_mulai', '').strip()
        tanggal_berakhir = request.POST.get('tanggal_berakhir', '').strip()
        
        # Validation
        if not all([nama_hadiah, harga_miles, deskripsi, id_penyedia, tanggal_mulai, tanggal_berakhir]):
            messages.error(request, 'Semua field wajib diisi.')
            return render(request, 'hadiah/tambah_hadiah.html', {'navbar_type': 'staff', 'staf': staf})
        
        try:
            harga_miles = int(harga_miles)
            if harga_miles <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Harga miles harus berupa angka positif.')
            return render(request, 'hadiah/tambah_hadiah.html', {'navbar_type': 'staff', 'staf': staf})
        
        try:
            # Generate reward code
            kode_hadiah = f"RWD-{int(timezone.now().timestamp()) % 10000:04d}"
            
            sql = """
                INSERT INTO HADIAH 
                (kode_hadiah, nama_hadiah, harga_miles, deskripsi, id_penyedia, tanggal_mulai, tanggal_berakhir)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            execute_raw_sql_update(sql, [
                kode_hadiah, nama_hadiah, harga_miles, deskripsi, 
                id_penyedia, tanggal_mulai, tanggal_berakhir
            ])
            
            messages.success(request, f'Hadiah {nama_hadiah} berhasil ditambahkan dengan kode {kode_hadiah}.')
            return redirect('red:daftar_hadiah')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
            return render(request, 'hadiah/tambah_hadiah.html', {'navbar_type': 'staff', 'staf': staf})
    
    # Fetch providers
    sql_providers = "SELECT id_penyedia, nama_penyedia FROM PENYEDIA ORDER BY nama_penyedia"
    providers = execute_raw_sql(sql_providers)
    
    context = {
        'staf': staf,
        'providers': providers,
        'navbar_type': 'staff',
    }
    return render(request, 'hadiah/tambah_hadiah.html', context)


@login_required_staff
@require_http_methods(["GET", "POST"])
def edit_hadiah(request):
    """U — Update existing reward."""
    staf = get_staf(request)
    kode_hadiah = request.GET.get('kode') or request.POST.get('kode_hadiah')
    
    # Fetch reward details
    sql = "SELECT * FROM HADIAH WHERE kode_hadiah = %s"
    rewards = execute_raw_sql(sql, [kode_hadiah])
    
    if not rewards:
        messages.error(request, 'Hadiah tidak ditemukan.')
        return redirect('red:daftar_hadiah')
    
    hadiah = rewards[0]
    
    if request.method == 'POST':
        nama_hadiah = request.POST.get('nama_hadiah', '').strip()
        harga_miles = request.POST.get('harga_miles', '').strip()
        deskripsi = request.POST.get('deskripsi', '').strip()
        id_penyedia = request.POST.get('id_penyedia', '').strip()
        tanggal_berakhir = request.POST.get('tanggal_berakhir', '').strip()
        
        if not all([nama_hadiah, harga_miles, deskripsi, id_penyedia, tanggal_berakhir]):
            messages.error(request, 'Semua field wajib diisi.')
            context = {'staf': staf, 'hadiah': hadiah, 'navbar_type': 'staff'}
            return render(request, 'hadiah/edit_hadiah.html', context)
        
        try:
            harga_miles = int(harga_miles)
            if harga_miles <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Harga miles harus berupa angka positif.')
            context = {'staf': staf, 'hadiah': hadiah, 'navbar_type': 'staff'}
            return render(request, 'hadiah/edit_hadiah.html', context)
        
        try:
            sql = """
                UPDATE HADIAH
                SET nama_hadiah = %s, harga_miles = %s, deskripsi = %s, 
                    id_penyedia = %s, tanggal_berakhir = %s
                WHERE kode_hadiah = %s
            """
            
            execute_raw_sql_update(sql, [
                nama_hadiah, harga_miles, deskripsi, id_penyedia, tanggal_berakhir, kode_hadiah
            ])
            
            messages.success(request, f'Hadiah {nama_hadiah} berhasil diperbarui.')
            return redirect('red:daftar_hadiah')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    # Fetch providers
    sql_providers = "SELECT id_penyedia, nama_penyedia FROM PENYEDIA ORDER BY nama_penyedia"
    providers = execute_raw_sql(sql_providers)
    
    context = {
        'staf': staf,
        'hadiah': hadiah,
        'providers': providers,
        'navbar_type': 'staff',
    }
    return render(request, 'hadiah/edit_hadiah.html', context)


@login_required_staff
@require_http_methods(["POST"])
def hapus_hadiah(request):
    """D — Delete reward."""
    staf = get_staf(request)
    kode_hadiah = request.POST.get('kode_hadiah', '').strip()
    
    if not kode_hadiah:
        messages.error(request, 'Kode hadiah tidak valid.')
        return redirect('red:daftar_hadiah')
    
    try:
        sql = "DELETE FROM HADIAH WHERE kode_hadiah = %s"
        execute_raw_sql_update(sql, [kode_hadiah])
        messages.success(request, 'Hadiah berhasil dihapus.')
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return redirect('red:daftar_hadiah')


# ===== PARTNER MANAGEMENT (Mitra) =====

@login_required_staff
def daftar_mitra(request):
    """R — Display list of all partners."""
    staf = get_staf(request)
    
    # Fetch partners using raw SQL
    sql = """
        SELECT 
            id_penyedia,
            nama_penyedia,
            email_penyedia,
            tanggal_kerja_sama
        FROM PENYEDIA
        ORDER BY tanggal_kerja_sama DESC
    """
    
    mitras = execute_raw_sql(sql)
    
    context = {
        'staf': staf,
        'mitras': mitras,
        'navbar_type': 'staff',
    }
    return render(request, 'mitra/daftar_mitra.html', context)


@login_required_staff
@require_http_methods(["GET", "POST"])
def tambah_mitra(request):
    """C — Create new partner."""
    staf = get_staf(request)
    
    if request.method == 'POST':
        nama_penyedia = request.POST.get('nama_penyedia', '').strip()
        email_penyedia = request.POST.get('email_penyedia', '').strip()
        tanggal_kerja_sama = request.POST.get('tanggal_kerja_sama', '').strip()
        
        # Validation
        if not all([nama_penyedia, email_penyedia, tanggal_kerja_sama]):
            messages.error(request, 'Semua field wajib diisi.')
            return render(request, 'mitra/tambah_mitra.html', {'navbar_type': 'staff', 'staf': staf})
        
        # Validate email format
        if '@' not in email_penyedia:
            messages.error(request, 'Format email tidak valid.')
            return render(request, 'mitra/tambah_mitra.html', {'navbar_type': 'staff', 'staf': staf})
        
        try:
            sql = """
                INSERT INTO PENYEDIA 
                (nama_penyedia, email_penyedia, tanggal_kerja_sama)
                VALUES (%s, %s, %s)
            """
            
            execute_raw_sql_update(sql, [nama_penyedia, email_penyedia, tanggal_kerja_sama])
            
            messages.success(request, f'Mitra {nama_penyedia} berhasil ditambahkan.')
            return redirect('red:daftar_mitra')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
            return render(request, 'mitra/tambah_mitra.html', {'navbar_type': 'staff', 'staf': staf})
    
    context = {
        'staf': staf,
        'navbar_type': 'staff',
    }
    return render(request, 'mitra/tambah_mitra.html', context)


@login_required_staff
@require_http_methods(["GET", "POST"])
def edit_mitra(request):
    """U — Update existing partner."""
    staf = get_staf(request)
    id_penyedia = request.GET.get('id') or request.POST.get('id_penyedia')
    
    # Fetch partner details
    sql = "SELECT * FROM PENYEDIA WHERE id_penyedia = %s"
    mitras = execute_raw_sql(sql, [id_penyedia])
    
    if not mitras:
        messages.error(request, 'Mitra tidak ditemukan.')
        return redirect('red:daftar_mitra')
    
    mitra = mitras[0]
    
    if request.method == 'POST':
        nama_penyedia = request.POST.get('nama_penyedia', '').strip()
        tanggal_kerja_sama = request.POST.get('tanggal_kerja_sama', '').strip()
        
        if not all([nama_penyedia, tanggal_kerja_sama]):
            messages.error(request, 'Semua field wajib diisi.')
            context = {'staf': staf, 'mitra': mitra, 'navbar_type': 'staff'}
            return render(request, 'mitra/edit_mitra.html', context)
        
        try:
            sql = """
                UPDATE PENYEDIA
                SET nama_penyedia = %s, tanggal_kerja_sama = %s
                WHERE id_penyedia = %s
            """
            
            execute_raw_sql_update(sql, [nama_penyedia, tanggal_kerja_sama, id_penyedia])
            
            messages.success(request, f'Mitra {nama_penyedia} berhasil diperbarui.')
            return redirect('red:daftar_mitra')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    context = {
        'staf': staf,
        'mitra': mitra,
        'navbar_type': 'staff',
    }
    return render(request, 'mitra/edit_mitra.html', context)


@login_required_staff
@require_http_methods(["POST"])
def hapus_mitra(request):
    """D — Delete partner."""
    staf = get_staf(request)
    id_penyedia = request.POST.get('id_penyedia', '').strip()
    
    if not id_penyedia:
        messages.error(request, 'ID Mitra tidak valid.')
        return redirect('red:daftar_mitra')
    
    try:
        sql = "DELETE FROM PENYEDIA WHERE id_penyedia = %s"
        execute_raw_sql_update(sql, [id_penyedia])
        messages.success(request, 'Mitra berhasil dihapus.')
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return redirect('red:daftar_mitra')