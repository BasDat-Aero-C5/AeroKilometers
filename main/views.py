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


def get_member_data(email):
    """Return Member data by email."""
    sql = """
        SELECT m.email, m.nomor_member, m.tanggal_bergabung, m.id_tier,
               m.award_miles, m.total_miles,
               p.first_mid_name, p.last_name, p.salutation,
               p.country_code, p.mobile_number,
               p.tanggal_lahir, p.kewarganegaraan
        FROM MEMBER m
        JOIN PENGGUNA p ON m.email = p.email
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
        FROM STAF s
        JOIN PENGGUNA p ON s.email = p.email
        JOIN MASKAPAI m ON s.kode_maskapai = m.kode_maskapai
        WHERE s.email = %s
    """
    result = execute_raw_sql(sql, [email])
    return result[0] if result else None


def get_member_transactions(email, limit=5):
    """Return recent transactions for a member."""
    sql = """
        SELECT 'Transfer' as type, tanggal_transfer as date, jumlah_miles * -1 as miles
        FROM TRANSFER
        WHERE email_member = %s
        UNION ALL
        SELECT 'Redeem' as type, tanggal_redeem as date, -jumlah_miles as miles
        FROM REDEEM
        WHERE email_member = %s
        UNION ALL
        SELECT 'Package' as type, timestamp as date, jumlah_miles as miles
        FROM MEMBER_AWARD_MILES_PACKAGE
        WHERE email_member = %s
        ORDER BY date DESC
        LIMIT %s
    """
    return execute_raw_sql(sql, [email, email, email, limit])


def get_staf_claim_stats(email):
    """Return claim statistics for a staff member."""
    sql = """
        SELECT 
            COUNT(CASE WHEN status = 'Menunggu' THEN 1 END) as pending,
            COUNT(CASE WHEN status = 'Disetujui' THEN 1 END) as approved,
            COUNT(CASE WHEN status = 'Ditolak' THEN 1 END) as rejected
        FROM CLAIM_MISSING_MILES
        WHERE email_staf = %s
    """
    result = execute_raw_sql(sql, [email])
    return result[0] if result else None


# Create your views here.
def homepage(request):
    return render(request, 'homepage.html')


def login(request):
    return render(request, 'login.html', {'navbar_type': 'guest'})


def register(request):
    return render(request, 'register.html', {'navbar_type': 'guest'})


def dashboard_member(request):
    email = request.session.get('email')
    
    if not email:
        return redirect('login')
    
    member = get_member_data(email)
    
    if not member:
        return redirect('login')
    
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
        return redirect('login')
    
    staf = get_staf_data(email)
    
    if not staf:
        return redirect('login')
    
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
        return redirect('login')
    
    if role == "member":
        member = get_member_data(email)
        if not member:
            return redirect('login')
        
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
            return redirect('login')
        
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
