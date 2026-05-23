from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import IntegrityError
from django.utils import timezone
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
    """Execute a raw INSERT/UPDATE/DELETE query."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = adapt_sql(sql)
        cursor.execute(sql, params or [])
        conn.commit()
        cursor.close()
        if settings.PRODUCTION:
            conn.close()
        return True
    except Exception as e:
        print(f"Database error: {e}")
        raise


def authenticate_pengguna(email, password):
    """Authenticate against the database using the stored function if available."""
    sql = "SELECT * FROM pengguna WHERE email = %s AND password = %s"
    rows = execute_raw_sql(sql, [email, password])
    return rows[0] if rows else None


def get_member_data(email):
    """Return Member data by email."""
    sql = """
        SELECT m.email, m.nomor_member, m.tanggal_bergabung, m.id_tier,
               m.award_miles, m.total_miles,
               p.first_mid_name, p.last_name, p.salutation,
               p.country_code, p.mobile_number,
               p.tanggal_lahir, p.kewarganegaraan
        FROM member m
        JOIN pengguna p ON m.email = p.email
        WHERE m.email = %s
    """
    result = execute_raw_sql(sql, [email])
    return result[0] if result else None


def get_staf_data(email):
    """Return Staf data by email."""
    sql = """
        SELECT s.email, s.id_staf, s.kode_maskapai,
               m.nama_maskapai,
               p.first_mid_name, p.last_name, p.salutation,
               p.country_code, p.mobile_number,
               p.tanggal_lahir, p.kewarganegaraan
        FROM staf s
        JOIN pengguna p ON s.email = p.email
        JOIN maskapai m ON s.kode_maskapai = m.kode_maskapai
        WHERE s.email = %s
    """
    result = execute_raw_sql(sql, [email])
    return result[0] if result else None


def get_member_transactions(email, limit=5):
    """Return recent transactions for a member."""
    sql = """
        SELECT 'Transfer' as type, timestamp as date, jumlah * -1 as miles
        FROM transfer
        WHERE email_member_1 = %s
        UNION ALL
        SELECT 'Redeem' as type, timestamp as date, 0 as miles
        FROM redeem
        WHERE email_member = %s
        UNION ALL
        SELECT 'Package' as type, timestamp as date, 0 as miles
        FROM member_award_miles_package
        WHERE email_member = %s
        ORDER BY date DESC
        LIMIT %s
    """
    return execute_raw_sql(sql, [email, email, email, limit])


def get_staf_claim_stats(email):
    """Return claim statistics for a staff member."""
    sql = """
        SELECT 
            COUNT(CASE WHEN status_penerimaan = 'Menunggu' THEN 1 END) as pending,
            COUNT(CASE WHEN status_penerimaan = 'Disetujui' THEN 1 END) as approved,
            COUNT(CASE WHEN status_penerimaan = 'Ditolak' THEN 1 END) as rejected
        FROM claim_missing_miles
        WHERE email_staf = %s
    """
    result = execute_raw_sql(sql, [email])
    return result[0] if result else None


def get_homepage_stats():
    """Return homepage statistic cards based on current DB counts."""
    queries = {
        'Member Aktif': "SELECT COUNT(*) as cnt FROM member",
        'Maskapai Partner': "SELECT COUNT(*) as cnt FROM maskapai",
        'Bandara Terhubung': "SELECT COUNT(*) as cnt FROM bandara",
        'Hadiah Menanti': "SELECT COUNT(*) as cnt FROM hadiah",
    }

    stats = []
    for label, sql in queries.items():
        rows = execute_raw_sql(sql)
        cnt = rows[0].get('cnt', 0) if rows else 0
        stats.append({'label': label, 'value': f"{cnt:,}"})

    return stats


# Create your views here.
def homepage(request):
    # Provide homepage statistics pulled from the database
    stats = get_homepage_stats()
    return render(request, 'homepage.html', {'stats_data': stats})


def login(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        if not email or not password:
            messages.error(request, 'Email dan password wajib diisi.')
            return render(request, 'login.html', {'navbar_type': 'guest'})

        try:
            pengguna = authenticate_pengguna(email, password)
            if not pengguna:
                messages.error(request, 'Email atau password salah.')
                return render(request, 'login.html', {'navbar_type': 'guest'})

            member_rows = execute_raw_sql('SELECT email FROM member WHERE email = %s', [email])
            staf_rows = execute_raw_sql('SELECT email FROM staf WHERE email = %s', [email])

            request.session['email'] = email
            if member_rows:
                request.session['role'] = 'member'
                return redirect('main:dashboard_member')
            if staf_rows:
                request.session['role'] = 'staff'
                return redirect('main:dashboard_staff')

            messages.error(request, 'Akun ditemukan tetapi tidak memiliki profil Member atau Staff.')
        except Exception as e:
            messages.error(request, str(e))

    return render(request, 'login.html', {'navbar_type': 'guest'})


def register(request):
    if request.method == 'POST':
        role = request.POST.get('role', 'member')
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('konfirmasi_password', '').strip()
        salutation = request.POST.get('salutation', '').strip()
        first_mid_name = request.POST.get('first_mid_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        country_code = request.POST.get('country_code', '').strip()
        mobile_number = request.POST.get('mobile_number', '').strip()
        tanggal_lahir = request.POST.get('tanggal_lahir', '').strip()
        kewarganegaraan = request.POST.get('kewarganegaraan', '').strip()
        kode_maskapai = request.POST.get('kode_maskapai', '').strip()

        if not all([email, password, confirm_password, salutation, first_mid_name, last_name, country_code, mobile_number, tanggal_lahir, kewarganegaraan]):
            messages.error(request, 'Semua field wajib diisi.')
            return render(request, 'register.html', {'navbar_type': 'guest'})

        if password != confirm_password:
            messages.error(request, 'Password dan konfirmasi password tidak cocok.')
            return render(request, 'register.html', {'navbar_type': 'guest'})

        if role == 'staf' and not kode_maskapai:
            messages.error(request, 'Kode maskapai wajib diisi untuk staf.')
            return render(request, 'register.html', {'navbar_type': 'guest'})

        try:
            sql_pengguna = (
                'INSERT INTO pengguna (email, password, salutation, first_mid_name, last_name, country_code, mobile_number, tanggal_lahir, kewarganegaraan) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)'
            )
            execute_raw_sql_update(sql_pengguna, [email, password, salutation, first_mid_name, last_name, country_code, mobile_number, tanggal_lahir, kewarganegaraan])

            if role == 'member':
                nomor_member = f'M{int(timezone.now().timestamp()) % 1000000:06d}'
                sql_member = (
                    'INSERT INTO member (email, nomor_member, tanggal_bergabung, id_tier, award_miles, total_miles) '
                    'VALUES (%s, %s, %s, %s, %s, %s)'
                )
                execute_raw_sql_update(sql_member, [email, nomor_member, timezone.now().date(), 'T1', 0, 0])
            else:
                id_staf = f'S{int(timezone.now().timestamp()) % 1000000:06d}'
                sql_staf = 'INSERT INTO staf (email, id_staf, kode_maskapai) VALUES (%s, %s, %s)'
                execute_raw_sql_update(sql_staf, [email, id_staf, kode_maskapai])

            messages.success(request, 'Pendaftaran berhasil. Silakan login.')
            return redirect('main:login')
        except Exception as e:
            error_message = str(e)
            if 'duplicate' in error_message.lower() or 'already exists' in error_message.lower() or 'sudah terdaftar' in error_message.lower():
                messages.error(request, 'Email sudah terdaftar. Gunakan email lain.')
            else:
                messages.error(request, error_message)

    return render(request, 'register.html', {'navbar_type': 'guest'})


def dashboard_member(request):
    email = request.session.get('email')
    
    if not email:
        return redirect('main:login')
    
    member = get_member_data(email)
    
    if not member:
        return redirect('main:login')
    
    transactions = get_member_transactions(email)
    
    # Format user data for template
    user_data = {
        "name": f"{member.get('salutation', '')} {member.get('first_mid_name', '')} {member.get('last_name', '')}".strip(),
        "email": member.get('email', ''),
        "phone": f"{member.get('country_code', '')} {member.get('mobile_number', '')}".strip(),
        "nationality": member.get('kewarganegaraan', ''),
        "birthdate": member.get('tanggal_lahir', ''),
        "joined": member.get('tanggal_bergabung', '')
    }
    
    member_data = {
        "member_id": member.get('nomor_member', ''),
        "tier": member.get('id_tier', ''),
        "total_miles": member.get('total_miles', 0),
        "award_miles": member.get('award_miles', 0),
        "transactions": [
            {
                "type": t.get('type', ''),
                "date": str(t.get('date', '')),
                "miles": f"{t.get('miles', 0):+d}"
            } for t in transactions
        ]
    }
    
    return render(request, "dashboard_member.html", {
        "role": "member",
        "user": user_data,
        "member": member_data,
    })



def dashboard_staff(request):
    email = request.session.get('email')
    
    if not email:
        return redirect('main:login')
    
    staf = get_staf_data(email)
    
    if not staf:
        return redirect('main:login')
    
    claim_stats = get_staf_claim_stats(email)
    
    # Format user data for template
    user_data = {
        "name": f"{staf.get('salutation', '')} {staf.get('first_mid_name', '')} {staf.get('last_name', '')}".strip(),
        "email": staf.get('email', ''),
        "phone": f"{staf.get('country_code', '')} {staf.get('mobile_number', '')}".strip(),
        "nationality": staf.get('kewarganegaraan', ''),
        "birthdate": staf.get('tanggal_lahir', ''),
        "joined": staf.get('tanggal_bergabung', '')
    }
    
    staff_data = {
        "staff_id": staf.get('id_staf', ''),
        "airline": staf.get('nama_maskapai', ''),
        "pending": claim_stats.get('pending', 0) if claim_stats else 0,
        "approved": claim_stats.get('approved', 0) if claim_stats else 0,
        "rejected": claim_stats.get('rejected', 0) if claim_stats else 0
    }
    
    return render(request, "dashboard_staff.html", {
        "role": "staff",
        "user": user_data,
        "staff": staff_data,
    })


def profile_view(request):
    email = request.session.get('email')
    role = request.GET.get("role", "member")
    
    if not email:
        return redirect('main:login')
    
    if role == "member":
        member = get_member_data(email)
        if not member:
            return redirect('main:login')
        
        user = {
            "email": member.get('email', ''),
            "member_id": member.get('nomor_member', ''),
            "joined": member.get('tanggal_bergabung', ''),
            "salutation": member.get('salutation', ''),
            "first": member.get('first_mid_name', '').split()[0] if member.get('first_mid_name') else '',
            "middle": ' '.join(member.get('first_mid_name', '').split()[1:]) if len(member.get('first_mid_name', '').split()) > 1 else '',
            "last": member.get('last_name', ''),
            "nationality": member.get('kewarganegaraan', ''),
            "country_code": member.get('country_code', ''),
            "phone": member.get('mobile_number', ''),
            "birthdate": member.get('tanggal_lahir', ''),
        }
    else:  # staff
        staf = get_staf_data(email)
        if not staf:
            return redirect('main:login')
        
        user = {
            "email": staf.get('email', ''),
            "staff_id": staf.get('id_staf', ''),
            "salutation": staf.get('salutation', ''),
            "first": staf.get('first_mid_name', '').split()[0] if staf.get('first_mid_name') else '',
            "middle": ' '.join(staf.get('first_mid_name', '').split()[1:]) if len(staf.get('first_mid_name', '').split()) > 1 else '',
            "last": staf.get('last_name', ''),
            "nationality": staf.get('kewarganegaraan', ''),
            "country_code": staf.get('country_code', ''),
            "phone": staf.get('mobile_number', ''),
            "birthdate": staf.get('tanggal_lahir', ''),
            "airline": staf.get('nama_maskapai', ''),
        }
    
    return render(request, "profile.html", {
        "user": user,
        "role": role
    })
