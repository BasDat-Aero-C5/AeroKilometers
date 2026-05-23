from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib.auth.hashers import make_password
from django.conf import settings
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from urllib.parse import urlparse


class DBRow(dict):
    def __getattr__(self, name):
        if name in self:
            return self[name]
        if name == 'pk' and 'id' in self:
            return self['id']
        if name == 'email_id' and 'email' in self:
            return self['email']
        if name == 'id_tier_id' and 'id_tier' in self:
            return self['id_tier']
        raise AttributeError(f"Attribute {name} not found")

    def __setattr__(self, name, value):
        self[name] = value


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
def get_member(request):
    """Return Member object for the logged-in user, or None."""
    email = request.session.get('email')
    role = request.session.get('role')
    
    if not email or role != 'member':
        return None

    sql = """
        SELECT m.email, m.nomor_member, m.tanggal_bergabung, m.id_tier,
               m.award_miles, m.total_miles,
               p.first_mid_name, p.last_name, p.salutation,
               p.country_code, p.mobile_number,
               p.tanggal_lahir, p.kewarganegaraan,
               m.email AS email_id
        FROM member m
        JOIN pengguna p ON m.email = p.email
        WHERE m.email = %s
    """
    rows = execute_raw_sql(sql, [email])
    return DBRow(rows[0]) if rows else None


def get_staf(request):
    """Return Staf object for the logged-in user, or None."""
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
    return DBRow(rows[0]) if rows else None


def login_required_member(view_func):
    """Decorator: redirect to login if not Member."""
    def wrapper(request, *args, **kwargs):
        if not get_member(request):
            messages.error(request, 'Silakan login sebagai Member terlebih dahulu.')
            return redirect('main:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def login_required_staff(view_func):
    """Decorator: redirect to login if not Staff."""
    def wrapper(request, *args, **kwargs):
        if not get_staf(request):
            messages.error(request, 'Silakan login sebagai Staff terlebih dahulu.')
            return redirect('main:login')
        return view_func(request, *args, **kwargs)
    return wrapper


# ===== Member Identity Management (Member) =====

@login_required_member
def page_view(request):
    """R — Display member's identities."""
    member = get_member(request)
    
    sql = """
        SELECT 
            nomor as nomor_dokumen,
            jenis as jenis_dokumen,
            negara_penerbit as negara,
            tanggal_terbit,
            tanggal_habis,
            CASE 
                WHEN tanggal_habis >= CURRENT_DATE THEN 'Aktif'
                ELSE 'Kedaluwarsa'
            END as status
        FROM identitas
        WHERE email_member = %s
        ORDER BY tanggal_terbit DESC
    """
    
    identities = execute_raw_sql(sql, [member.email_id])
    
    return render(request, 'member/page.html', {
        'member': member,
        'identities': identities,
        'navbar_type': 'member',
    })


@login_required_member
@require_http_methods(["GET", "POST"])
def form_view_member(request):
    """C — Create new member identity."""
    member = get_member(request)
    
    if request.method == 'POST':
        nomor_dokumen = request.POST.get('nomor_dokumen', '').strip()
        jenis_dokumen = request.POST.get('jenis_dokumen', '').strip()
        negara = request.POST.get('negara', '').strip()
        tanggal_terbit = request.POST.get('tanggal_terbit', '').strip()
        tanggal_habis = request.POST.get('tanggal_habis', '').strip()
        
        if not all([nomor_dokumen, jenis_dokumen, negara, tanggal_terbit, tanggal_habis]):
            messages.error(request, 'Semua field wajib diisi.')
            return render(request, 'member/form_create_member.html', {
                'member': member,
                'navbar_type': 'member'
            })
        
        try:
            sql = """
                INSERT INTO identitas
                (email_member, nomor, jenis, negara_penerbit, tanggal_terbit, tanggal_habis)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            execute_raw_sql_update(sql, [
                member.email_id, nomor_dokumen, jenis_dokumen, 
                negara, tanggal_terbit, tanggal_habis
            ])
            
            messages.success(request, f'Identitas {jenis_dokumen} berhasil ditambahkan.')
            return redirect('yellow:page')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
            return render(request, 'member/form_create_member.html', {
                'member': member,
                'navbar_type': 'member'
            })
    
    return render(request, 'member/form_create_member.html', {
        'member': member,
        'navbar_type': 'member'
    })


@login_required_member
@require_http_methods(["GET", "POST"])
def edit_view_member(request, id):
    """U — Update member identity."""
    member = get_member(request)
    
    sql = """
        SELECT nomor as nomor_dokumen, jenis as jenis_dokumen,
               negara_penerbit as negara, tanggal_terbit, tanggal_habis,
               email_member
        FROM identitas
        WHERE nomor = %s AND email_member = %s
    """
    identities = execute_raw_sql(sql, [id, member.email_id])
    
    if not identities:
        messages.error(request, 'Identitas tidak ditemukan.')
        return redirect('yellow:page')
    
    identity = identities[0]
    
    if request.method == 'POST':
        jenis_dokumen = request.POST.get('jenis_dokumen', '').strip()
        negara = request.POST.get('negara', '').strip()
        tanggal_terbit = request.POST.get('tanggal_terbit', '').strip()
        tanggal_habis = request.POST.get('tanggal_habis', '').strip()
        
        if not all([jenis_dokumen, negara, tanggal_terbit, tanggal_habis]):
            messages.error(request, 'Semua field wajib diisi.')
            context = {'member': member, 'identity': identity, 'navbar_type': 'member'}
            return render(request, 'member/form_edit_member.html', context)
        
        try:
            sql = """
                UPDATE identitas
                SET jenis = %s, negara_penerbit = %s, tanggal_terbit = %s, tanggal_habis = %s
                WHERE nomor = %s AND email_member = %s
            """
            
            execute_raw_sql_update(sql, [
                jenis_dokumen, negara, tanggal_terbit, tanggal_habis, id, member.email_id
            ])
            
            messages.success(request, 'Identitas berhasil diperbarui.')
            return redirect('yellow:page')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    context = {'member': member, 'identity': identity, 'navbar_type': 'member'}
    return render(request, 'member/form_edit_member.html', context)


# ===== Member Data Management (Staff) =====

@login_required_staff
def staff_page_view(request):
    """R — Display list of all members (for staff)."""
    staf = get_staf(request)
    
    sql = """
        SELECT 
            m.email,
            m.nomor_member,
            CONCAT(p.first_mid_name, ' ', p.last_name) as nama,
            p.email as email_pengguna,
            t.nama as tier,
            m.total_miles,
            m.award_miles,
            m.tanggal_bergabung
        FROM member m
        JOIN pengguna p ON m.email = p.email
        JOIN tier t ON m.id_tier = t.id_tier
        ORDER BY m.tanggal_bergabung DESC
    """
    
    members = execute_raw_sql(sql)
    
    return render(request, 'member/staff_page.html', {
        'staf': staf,
        'members': members,
        'navbar_type': 'staff',
    })


@login_required_staff
@require_http_methods(["GET", "POST"])
def form_view_staff(request):
    """C — Create new member (staff action)."""
    staf = get_staf(request)
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        nomor_member = request.POST.get('nomor_member', '').strip()
        salutation = request.POST.get('salutation', '').strip()
        nama_depan = request.POST.get('nama_depan', '').strip()
        nama_tengah = request.POST.get('nama_tengah', '').strip()
        nama_belakang = request.POST.get('nama_belakang', '').strip()
        kewarganegaraan = request.POST.get('kewarganegaraan', '').strip()
        country_code = request.POST.get('country_code', '').strip()
        nomor_hp = request.POST.get('nomor_hp', '').strip()
        tanggal_lahir = request.POST.get('tanggal_lahir', '').strip()
        tier = request.POST.get('tier', '').strip()
        
        if not all([email, password, nomor_member, salutation, nama_depan, 
                    nama_belakang, kewarganegaraan, country_code, nomor_hp, 
                    tanggal_lahir, tier]):
            messages.error(request, 'Semua field wajib diisi.')
            return render(request, 'member/form_create_staff.html', {'navbar_type': 'staff', 'staf': staf})
        
        if len(password) < 8:
            messages.error(request, 'Password minimal 8 karakter.')
            return render(request, 'member/form_create_staff.html', {'navbar_type': 'staff', 'staf': staf})
        
        try:
            sql_pengguna = """
                INSERT INTO pengguna
                (email, password, salutation, first_mid_name, last_name, country_code, mobile_number, tanggal_lahir, kewarganegaraan)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            execute_raw_sql_update(sql_pengguna, [
                email, make_password(password), salutation, nama_depan, nama_belakang,
                country_code, nomor_hp, tanggal_lahir, kewarganegaraan
            ])
            
            sql_member = """
                INSERT INTO member
                (email, nomor_member, tanggal_bergabung, id_tier, award_miles, total_miles)
                VALUES (%s, %s, %s, %s, 0, 0)
            """
            
            execute_raw_sql_update(sql_member, [
                email, nomor_member, timezone.now().date(), tier
            ])
            
            messages.success(request, f'Member {email} berhasil ditambahkan.')
            return redirect('yellow:staff_page')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
            return render(request, 'member/form_create_staff.html', {'navbar_type': 'staff', 'staf': staf})
    
    sql_tiers = "SELECT id_tier, nama FROM tier ORDER BY nama"
    tiers = execute_raw_sql(sql_tiers)
    
    context = {
        'staf': staf,
        'tiers': tiers,
        'navbar_type': 'staff',
    }
    return render(request, 'member/form_create_staff.html', context)


@login_required_staff
@require_http_methods(["GET", "POST"])
def edit_view_staff(request, id):
    """U — Update member data (staff action)."""
    staf = get_staf(request)
    
    sql = """
        SELECT 
            m.email,
            m.nomor_member,
            p.salutation,
            p.first_mid_name,
            p.last_name,
            p.country_code,
            p.mobile_number,
            p.tanggal_lahir,
            p.kewarganegaraan,
            m.id_tier,
            m.total_miles,
            m.award_miles
        FROM member m
        JOIN pengguna p ON m.email = p.email
        WHERE m.email = %s
    """
    
    members = execute_raw_sql(sql, [id])
    
    if not members:
        messages.error(request, 'Member tidak ditemukan.')
        return redirect('yellow:staff_page')
    
    member = members[0]
    
    if request.method == 'POST':
        salutation = request.POST.get('salutation', '').strip()
        nama_depan = request.POST.get('nama_depan', '').strip()
        nama_tengah = request.POST.get('nama_tengah', '').strip()
        nama_belakang = request.POST.get('nama_belakang', '').strip()
        kewarganegaraan = request.POST.get('kewarganegaraan', '').strip()
        country_code = request.POST.get('country_code', '').strip()
        nomor_hp = request.POST.get('nomor_hp', '').strip()
        tanggal_lahir = request.POST.get('tanggal_lahir', '').strip()
        tier = request.POST.get('tier', '').strip()
        
        if not all([salutation, nama_depan, nama_belakang, kewarganegaraan, 
                    country_code, nomor_hp, tanggal_lahir, tier]):
            messages.error(request, 'Semua field wajib diisi.')
            context = {'staf': staf, 'member': member, 'navbar_type': 'staff'}
            return render(request, 'member/form_edit_staff.html', context)
        
        try:
            sql_update = """
                UPDATE pengguna
                SET salutation = %s, first_mid_name = %s, last_name = %s,
                    country_code = %s, mobile_number = %s, tanggal_lahir = %s, kewarganegaraan = %s
                WHERE email = %s
            """
            
            execute_raw_sql_update(sql_update, [
                salutation, nama_depan, nama_belakang, country_code, 
                nomor_hp, tanggal_lahir, kewarganegaraan, id
            ])
            
            sql_tier = "UPDATE member SET id_tier = %s WHERE email = %s"
            execute_raw_sql_update(sql_tier, [tier, id])
            
            messages.success(request, f'Data member {id} berhasil diperbarui.')
            return redirect('yellow:staff_page')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    sql_tiers = "SELECT id_tier, nama FROM tier ORDER BY nama"
    tiers = execute_raw_sql(sql_tiers)
    
    context = {
        'staf': staf,
        'member': member,
        'tiers': tiers,
        'navbar_type': 'staff',
    }
    return render(request, 'member/form_edit_staff.html', context)


# ===== Member Identity Management (Member) =====

@login_required_member
def page_view(request):
    """R — Display member's identities."""
    member = get_member(request)
    
    # Fetch member identities using raw SQL
    sql = """
        SELECT 
            nomor as nomor_dokumen,
            jenis as jenis_dokumen,
            negara_penerbit as negara,
            tanggal_terbit,
            tanggal_habis,
            CASE 
                WHEN tanggal_habis >= CURRENT_DATE THEN 'Aktif'
                ELSE 'Kedaluwarsa'
            END as status
        FROM identitas
        WHERE email_member = %s
        ORDER BY tanggal_terbit DESC
    """
    
    identities = execute_raw_sql(sql, [member.email_id])
    
    return render(request, 'member/page.html', {
        'member': member,
        'identities': identities,
        'navbar_type': 'member',
    })


@login_required_member
@require_http_methods(["GET", "POST"])
def form_view_member(request):
    """C — Create new member identity."""
    member = get_member(request)
    
    if request.method == 'POST':
        nomor_dokumen = request.POST.get('nomor_dokumen', '').strip()
        jenis_dokumen = request.POST.get('jenis_dokumen', '').strip()
        negara = request.POST.get('negara', '').strip()
        tanggal_terbit = request.POST.get('tanggal_terbit', '').strip()
        tanggal_habis = request.POST.get('tanggal_habis', '').strip()
        
        # Validation
        if not all([nomor_dokumen, jenis_dokumen, negara, tanggal_terbit, tanggal_habis]):
            messages.error(request, 'Semua field wajib diisi.')
            return render(request, 'member/form_create_member.html', {
                'member': member,
                'navbar_type': 'member'
            })
        
        try:
            sql = """
                INSERT INTO identitas
                (email_member, nomor, jenis, negara_penerbit, tanggal_terbit, tanggal_habis)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            execute_raw_sql_update(sql, [
                member.email_id, nomor_dokumen, jenis_dokumen, 
                negara, tanggal_terbit, tanggal_habis
            ])
            
            messages.success(request, f'Identitas {jenis_dokumen} berhasil ditambahkan.')
            return redirect('yellow:page')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
            return render(request, 'member/form_create_member.html', {
                'member': member,
                'navbar_type': 'member'
            })
    
    return render(request, 'member/form_create_member.html', {
        'member': member,
        'navbar_type': 'member'
    })


@login_required_member
@require_http_methods(["GET", "POST"])
def edit_view_member(request, id):
    """U — Update member identity."""
    member = get_member(request)
    
    # Fetch identity
    sql = """
        SELECT nomor as nomor_dokumen, jenis as jenis_dokumen,
               negara_penerbit as negara, tanggal_terbit, tanggal_habis,
               email_member
        FROM identitas
        WHERE nomor = %s AND email_member = %s
    """
    identities = execute_raw_sql(sql, [id, member.email_id])
    
    if not identities:
        messages.error(request, 'Identitas tidak ditemukan.')
        return redirect('yellow:page')
    
    identity = identities[0]
    
    if request.method == 'POST':
        jenis_dokumen = request.POST.get('jenis_dokumen', '').strip()
        negara = request.POST.get('negara', '').strip()
        tanggal_terbit = request.POST.get('tanggal_terbit', '').strip()
        tanggal_habis = request.POST.get('tanggal_habis', '').strip()
        
        if not all([jenis_dokumen, negara, tanggal_terbit, tanggal_habis]):
            messages.error(request, 'Semua field wajib diisi.')
            context = {'member': member, 'identity': identity, 'navbar_type': 'member'}
            return render(request, 'member/form_edit_member.html', context)
        
        try:
            sql = """
                UPDATE identitas
                SET jenis = %s, negara_penerbit = %s, tanggal_terbit = %s, tanggal_habis = %s
                WHERE nomor = %s AND email_member = %s
            """
            
            execute_raw_sql_update(sql, [
                jenis_dokumen, negara, tanggal_terbit, tanggal_habis, id, member.email_id
            ])
            
            messages.success(request, 'Identitas berhasil diperbarui.')
            return redirect('yellow:page')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    context = {'member': member, 'identity': identity, 'navbar_type': 'member'}
    return render(request, 'member/form_edit_member.html', context)


# ===== Member Data Management (Staff) =====

@login_required_staff
def staff_page_view(request):
    """R — Display list of all members (for staff)."""
    staf = get_staf(request)
    
    # Fetch members with their tiers
    sql = """
        SELECT 
            m.email,
            m.nomor_member,
            CONCAT(p.first_mid_name, ' ', p.last_name) as nama,
            p.email as email_pengguna,
            t.nama as tier,
            m.total_miles,
            m.award_miles,
            m.tanggal_bergabung
        FROM member m
        JOIN pengguna p ON m.email = p.email
        JOIN tier t ON m.id_tier = t.id_tier
        ORDER BY m.tanggal_bergabung DESC
    """
    
    members = execute_raw_sql(sql)
    
    return render(request, 'member/staff_page.html', {
        'staf': staf,
        'members': members,
        'navbar_type': 'staff',
    })


@login_required_staff
@require_http_methods(["GET", "POST"])
def form_view_staff(request):
    """C — Create new member (staff action)."""
    staf = get_staf(request)
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        nomor_member = request.POST.get('nomor_member', '').strip()
        salutation = request.POST.get('salutation', '').strip()
        nama_depan = request.POST.get('nama_depan', '').strip()
        nama_tengah = request.POST.get('nama_tengah', '').strip()
        nama_belakang = request.POST.get('nama_belakang', '').strip()
        kewarganegaraan = request.POST.get('kewarganegaraan', '').strip()
        country_code = request.POST.get('country_code', '').strip()
        nomor_hp = request.POST.get('nomor_hp', '').strip()
        tanggal_lahir = request.POST.get('tanggal_lahir', '').strip()
        tier = request.POST.get('tier', '').strip()
        
        # Validation
        if not all([email, password, nomor_member, salutation, nama_depan, 
                    nama_belakang, kewarganegaraan, country_code, nomor_hp, 
                    tanggal_lahir, tier]):
            messages.error(request, 'Semua field wajib diisi.')
            return render(request, 'member/form_create_staff.html', {'navbar_type': 'staff', 'staf': staf})
        
        if len(password) < 8:
            messages.error(request, 'Password minimal 8 karakter.')
            return render(request, 'member/form_create_staff.html', {'navbar_type': 'staff', 'staf': staf})
        
        try:
            # Create pengguna
            sql_pengguna = """
                INSERT INTO pengguna
                (email, password, salutation, first_mid_name, last_name, country_code, mobile_number, tanggal_lahir, kewarganegaraan)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            execute_raw_sql_update(sql_pengguna, [
                email, make_password(password), salutation, nama_depan, nama_belakang,
                country_code, nomor_hp, tanggal_lahir, kewarganegaraan
            ])
            
            # Create member
            sql_member = """
                INSERT INTO member
                (email, nomor_member, tanggal_bergabung, id_tier, award_miles, total_miles)
                VALUES (%s, %s, %s, %s, 0, 0)
            """
            
            execute_raw_sql_update(sql_member, [
                email, nomor_member, timezone.now().date(), tier
            ])
            
            messages.success(request, f'Member {email} berhasil ditambahkan.')
            return redirect('yellow:staff_page')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
            return render(request, 'member/form_create_staff.html', {'navbar_type': 'staff', 'staf': staf})
    
    # Fetch tiers
    sql_tiers = "SELECT id_tier, nama FROM tier ORDER BY nama"
    tiers = execute_raw_sql(sql_tiers)
    
    context = {
        'staf': staf,
        'tiers': tiers,
        'navbar_type': 'staff',
    }
    return render(request, 'member/form_create_staff.html', context)


@login_required_staff
@require_http_methods(["GET", "POST"])
def edit_view_staff(request, id):
    """U — Update member data (staff action)."""
    staf = get_staf(request)
    
    # Fetch member
    sql = """
        SELECT 
            m.email,
            m.nomor_member,
            p.salutation,
            p.first_mid_name,
            p.last_name,
            p.country_code,
            p.mobile_number,
            p.tanggal_lahir,
            p.kewarganegaraan,
            m.id_tier,
            m.total_miles,
            m.award_miles
        FROM member m
        JOIN pengguna p ON m.email = p.email
        WHERE m.email = %s
    """
    
    members = execute_raw_sql(sql, [id])
    
    if not members:
        messages.error(request, 'Member tidak ditemukan.')
        return redirect('yellow:staff_page')
    
    member = members[0]
    
    if request.method == 'POST':
        salutation = request.POST.get('salutation', '').strip()
        nama_depan = request.POST.get('nama_depan', '').strip()
        nama_tengah = request.POST.get('nama_tengah', '').strip()
        nama_belakang = request.POST.get('nama_belakang', '').strip()
        kewarganegaraan = request.POST.get('kewarganegaraan', '').strip()
        country_code = request.POST.get('country_code', '').strip()
        nomor_hp = request.POST.get('nomor_hp', '').strip()
        tanggal_lahir = request.POST.get('tanggal_lahir', '').strip()
        tier = request.POST.get('tier', '').strip()
        
        if not all([salutation, nama_depan, nama_belakang, kewarganegaraan, 
                    country_code, nomor_hp, tanggal_lahir, tier]):
            messages.error(request, 'Semua field wajib diisi.')
            context = {'staf': staf, 'member': member, 'navbar_type': 'staff'}
            return render(request, 'member/form_edit_staff.html', context)
        
        try:
            # Update pengguna
            sql_update = """
                UPDATE pengguna
                SET salutation = %s, first_mid_name = %s, last_name = %s,
                    country_code = %s, mobile_number = %s, tanggal_lahir = %s, kewarganegaraan = %s
                WHERE email = %s
            """
            
            execute_raw_sql_update(sql_update, [
                salutation, nama_depan, nama_belakang, country_code, 
                nomor_hp, tanggal_lahir, kewarganegaraan, id
            ])
            
            # Update member tier
            sql_tier = "UPDATE member SET id_tier = %s WHERE email = %s"
            execute_raw_sql_update(sql_tier, [tier, id])
            
            messages.success(request, f'Data member {id} berhasil diperbarui.')
            return redirect('yellow:staff_page')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    # Fetch tiers
    sql_tiers = "SELECT id_tier, nama FROM tier ORDER BY nama"
    tiers = execute_raw_sql(sql_tiers)
    
    context = {
        'staf': staf,
        'member': member,
        'tiers': tiers,
        'navbar_type': 'staff',
    }
    return render(request, 'member/form_edit_staff.html', context)


