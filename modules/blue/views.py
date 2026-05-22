from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
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
        FROM MEMBER m
        JOIN PENGGUNA p ON m.email = p.email
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
        FROM STAF s
        JOIN PENGGUNA p ON s.email = p.email
        JOIN MASKAPAI m ON s.kode_maskapai = m.kode_maskapai
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


# ===== REWARDS REDEEM (Member) =====

@login_required_member
def redeem_hadiah(request):
    """CR — Redeem rewards with award miles."""
    member = get_member(request)
    tab = request.GET.get("tab", "katalog")
    
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
        WHERE tanggal_mulai <= CURDATE() AND tanggal_berakhir >= CURDATE()
        ORDER BY tanggal_mulai DESC
    """
    
    rewards = execute_raw_sql(sql)
    
    sql_history = """
        SELECT 
            rh.kode_hadiah,
            h.nama_hadiah,
            rh.tanggal_redeem as tanggal,
            h.harga_miles as miles
        FROM RIWAYAT_REDEEM rh
        JOIN HADIAH h ON rh.kode_hadiah = h.kode_hadiah
        WHERE rh.email_member = %s
        ORDER BY rh.tanggal_redeem DESC
        LIMIT 20
    """
    
    history = execute_raw_sql(sql_history, [member.email_id])
    
    context = {
        'member': member,
        'tab': tab,
        'rewards': rewards,
        'history': history,
        'user_miles': member.award_miles,
        'navbar_type': 'member',
    }
    return render(request, 'hadiah/redeem_hadiah.html', context)


@login_required_member
@require_http_methods(["POST"])
def redeem_confirm(request):
    """Process reward redemption."""
    member = get_member(request)
    kode_hadiah = request.POST.get('kode_hadiah', '').strip()
    
    if not kode_hadiah:
        messages.error(request, 'Kode hadiah tidak valid.')
        return redirect('blue:redeem_hadiah')
    
    sql = "SELECT * FROM HADIAH WHERE kode_hadiah = %s"
    hadiaha_list = execute_raw_sql(sql, [kode_hadiah])
    
    if not hadiaha_list:
        messages.error(request, 'Hadiah tidak ditemukan.')
        return redirect('blue:redeem_hadiah')
    
    hadiah = hadiaha_list[0]
    harga_miles = hadiah['harga_miles']
    
    if member.award_miles < harga_miles:
        messages.error(request, f'Award miles Anda tidak mencukupi. Diperlukan: {harga_miles}, Tersedia: {member.award_miles}')
        return redirect('blue:redeem_hadiah')
    
    try:
        sql_redeem = """
            INSERT INTO RIWAYAT_REDEEM (email_member, kode_hadiah, tanggal_redeem)
            VALUES (%s, %s, %s)
        """
        execute_raw_sql_update(sql_redeem, [member.email_id, kode_hadiah, timezone.now()])
        
        member.award_miles -= harga_miles
        sql_update_miles = "UPDATE MEMBER SET award_miles = award_miles - %s WHERE email = %s"
        execute_raw_sql_update(sql_update_miles, [harga_miles, member.email_id])
        
        messages.success(request, f'Hadiah berhasil ditukar. {harga_miles} award miles dikurangi dari akun Anda.')
        
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return redirect('blue:redeem_hadiah')


# ===== AWARD MILES PACKAGE (Member) =====

@login_required_member
def package_list(request):
    """CR — Display and buy award miles packages."""
    member = get_member(request)
    
    packages = [
        {"code": "AMP-001", "miles": 1000, "price": 150000},
        {"code": "AMP-002", "miles": 5000, "price": 650000},
        {"code": "AMP-003", "miles": 10000, "price": 1200000},
        {"code": "AMP-004", "miles": 25000, "price": 2750000},
    ]
    
    context = {
        'member': member,
        'packages': packages,
        'current_miles': member.award_miles,
        'navbar_type': 'member',
    }
    return render(request, 'hadiah/package_list.html', context)


@login_required_member
@require_http_methods(["POST"])
def buy_package(request):
    """Process package purchase."""
    member = get_member(request)
    kode_package = request.POST.get('kode_package', '').strip()
    
    packages = {
        "AMP-001": {"miles": 1000, "price": 150000},
        "AMP-002": {"miles": 5000, "price": 650000},
        "AMP-003": {"miles": 10000, "price": 1200000},
        "AMP-004": {"miles": 25000, "price": 2750000},
    }
    
    if kode_package not in packages:
        messages.error(request, 'Paket tidak valid.')
        return redirect('blue:package_list')
    
    package = packages[kode_package]
    
    try:
        sql_purchase = """
            INSERT INTO PEMBELIAN_MILES (email_member, kode_package, jumlah_miles, tanggal_pembelian)
            VALUES (%s, %s, %s, %s)
        """
        execute_raw_sql_update(sql_purchase, [
            member.email_id, kode_package, package['miles'], timezone.now()
        ])
        
        member.award_miles += package['miles']
        member.total_miles += package['miles']
        sql_update_miles = "UPDATE MEMBER SET award_miles = award_miles + %s, total_miles = total_miles + %s WHERE email = %s"
        execute_raw_sql_update(sql_update_miles, [package['miles'], package['miles'], member.email_id])
        
        messages.success(request, f'Paket {package["miles"]} miles berhasil dibeli!')
        
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return redirect('blue:package_list')


# ===== TIER INFORMATION (Member) =====

@login_required_member
def tier_info(request):
    """R — Display tier information and benefits."""
    member = get_member(request)
    
    sql = """
        SELECT 
            id_tier,
            nama as tier_name,
            minimal_frekuensi_terbang,
            minimal_tier_miles
        FROM TIER
        ORDER BY minimal_tier_miles ASC
    """
    
    tiers = execute_raw_sql(sql)
    
    sql_member_tier = """
        SELECT t.id_tier, t.nama as tier_name
        FROM TIER t
        WHERE t.id_tier = %s
    """
    
    current_tier_list = execute_raw_sql(sql_member_tier, [member.id_tier_id])
    current_tier = current_tier_list[0] if current_tier_list else None
    
    context = {
        'member': member,
        'tiers': tiers,
        'current_tier': current_tier,
        'navbar_type': 'member',
    }
    return render(request, 'hadiah/tier.html', context)


# ===== REPORTS & TRANSACTION HISTORY (Staff) =====

@login_required_staff
def report_view(request):
    """RD — Display miles transaction reports and history."""
    staf = get_staf(request)
    
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    transaction_type = request.GET.get('type', 'semua')
    
    sql = """
        SELECT 
            'Redeem' as tipe,
            email_member,
            kode_hadiah as reference,
            -harga_miles as miles,
            tanggal_redeem as tanggal
        FROM RIWAYAT_REDEEM
        WHERE 1=1
    """
    
    params = []
    
    if transaction_type in ['redeem', 'semua']:
        if start_date:
            sql += " AND tanggal_redeem >= %s"
            params.append(start_date)
        if end_date:
            sql += " AND tanggal_redeem <= %s"
            params.append(end_date)
    
    if transaction_type in ['transfer', 'semua']:
        sql += """
            UNION ALL
            SELECT 
                'Transfer Keluar' as tipe,
                email_member_1 as email_member,
                email_member_2 as reference,
                -jumlah as miles,
                timestamp as tanggal
            FROM TRANSFER
            WHERE 1=1
        """
        if start_date:
            sql += " AND timestamp >= %s"
            params.append(start_date) if not (transaction_type in ['redeem'] and start_date in params) else None
        if end_date:
            sql += " AND timestamp <= %s"
            params.append(end_date) if not (transaction_type in ['redeem'] and end_date in params) else None
    
    sql += " ORDER BY tanggal DESC LIMIT 500"
    
    transactions = execute_raw_sql(sql, params) if params else execute_raw_sql(sql)
    
    sql_summary = """
        SELECT 
            COUNT(*) as total_transactions,
            SUM(CASE WHEN tanggal_redeem IS NOT NULL THEN 1 ELSE 0 END) as total_redeems
        FROM RIWAYAT_REDEEM
    """
    
    summary_list = execute_raw_sql(sql_summary)
    summary = summary_list[0] if summary_list else {'total_transactions': 0, 'total_redeems': 0}
    
    context = {
        'staf': staf,
        'transactions': transactions,
        'summary': summary,
        'start_date': start_date,
        'end_date': end_date,
        'transaction_type': transaction_type,
        'navbar_type': 'staff',
    }
    return render(request, 'transfer/report.html', context)


# ===== REWARDS REDEEM (Member) =====

@login_required_member
def redeem_hadiah(request):
    """CR — Redeem rewards with award miles."""
    member = get_member(request)
    tab = request.GET.get("tab", "katalog")
    
    # Fetch available rewards
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
        WHERE tanggal_mulai <= CURDATE() AND tanggal_berakhir >= CURDATE()
        ORDER BY tanggal_mulai DESC
    """
    
    rewards = execute_raw_sql(sql)
    
    # Fetch redemption history
    sql_history = """
        SELECT 
            rh.kode_hadiah,
            h.nama_hadiah,
            rh.tanggal_redeem as tanggal,
            h.harga_miles as miles
        FROM RIWAYAT_REDEEM rh
        JOIN HADIAH h ON rh.kode_hadiah = h.kode_hadiah
        WHERE rh.email_member = %s
        ORDER BY rh.tanggal_redeem DESC
        LIMIT 20
    """
    
    history = execute_raw_sql(sql_history, [member.email_id])
    
    context = {
        'member': member,
        'tab': tab,
        'rewards': rewards,
        'history': history,
        'user_miles': member.award_miles,
        'navbar_type': 'member',
    }
    return render(request, 'hadiah/redeem_hadiah.html', context)


@login_required_member
@require_http_methods(["POST"])
def redeem_confirm(request):
    """Process reward redemption."""
    member = get_member(request)
    kode_hadiah = request.POST.get('kode_hadiah', '').strip()
    
    if not kode_hadiah:
        messages.error(request, 'Kode hadiah tidak valid.')
        return redirect('blue:redeem_hadiah')
    
    # Fetch hadiah details
    sql = "SELECT * FROM HADIAH WHERE kode_hadiah = %s"
    hadiaha_list = execute_raw_sql(sql, [kode_hadiah])
    
    if not hadiaha_list:
        messages.error(request, 'Hadiah tidak ditemukan.')
        return redirect('blue:redeem_hadiah')
    
    hadiah = hadiaha_list[0]
    harga_miles = hadiah['harga_miles']
    
    # Check if member has enough award miles
    if member.award_miles < harga_miles:
        messages.error(request, f'Award miles Anda tidak mencukupi. Diperlukan: {harga_miles}, Tersedia: {member.award_miles}')
        return redirect('blue:redeem_hadiah')
    
    try:
        # Record redemption
        sql_redeem = """
            INSERT INTO RIWAYAT_REDEEM (email_member, kode_hadiah, tanggal_redeem)
            VALUES (%s, %s, %s)
        """
        execute_raw_sql_update(sql_redeem, [member.email_id, kode_hadiah, timezone.now()])
        
        # Deduct award miles
        member.award_miles -= harga_miles
        sql_update_miles = "UPDATE MEMBER SET award_miles = award_miles - %s WHERE email = %s"
        execute_raw_sql_update(sql_update_miles, [harga_miles, member.email_id])
        
        messages.success(request, f'Hadiah berhasil ditukar. {harga_miles} award miles dikurangi dari akun Anda.')
        
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return redirect('blue:redeem_hadiah')


# ===== AWARD MILES PACKAGE (Member) =====

@login_required_member
def package_list(request):
    """CR — Display and buy award miles packages."""
    member = get_member(request)
    
    # Package options
    packages = [
        {"code": "AMP-001", "miles": 1000, "price": 150000},
        {"code": "AMP-002", "miles": 5000, "price": 650000},
        {"code": "AMP-003", "miles": 10000, "price": 1200000},
        {"code": "AMP-004", "miles": 25000, "price": 2750000},
    ]
    
    context = {
        'member': member,
        'packages': packages,
        'current_miles': member.award_miles,
        'navbar_type': 'member',
    }
    return render(request, 'hadiah/package_list.html', context)


@login_required_member
@require_http_methods(["POST"])
def buy_package(request):
    """Process package purchase."""
    member = get_member(request)
    kode_package = request.POST.get('kode_package', '').strip()
    
    # Validate package
    packages = {
        "AMP-001": {"miles": 1000, "price": 150000},
        "AMP-002": {"miles": 5000, "price": 650000},
        "AMP-003": {"miles": 10000, "price": 1200000},
        "AMP-004": {"miles": 25000, "price": 2750000},
    }
    
    if kode_package not in packages:
        messages.error(request, 'Paket tidak valid.')
        return redirect('blue:package_list')
    
    package = packages[kode_package]
    
    try:
        # Record purchase
        sql_purchase = """
            INSERT INTO PEMBELIAN_MILES (email_member, kode_package, jumlah_miles, tanggal_pembelian)
            VALUES (%s, %s, %s, %s)
        """
        execute_raw_sql_update(sql_purchase, [
            member.email_id, kode_package, package['miles'], timezone.now()
        ])
        
        # Add award miles
        member.award_miles += package['miles']
        member.total_miles += package['miles']
        sql_update_miles = "UPDATE MEMBER SET award_miles = award_miles + %s, total_miles = total_miles + %s WHERE email = %s"
        execute_raw_sql_update(sql_update_miles, [package['miles'], package['miles'], member.email_id])
        
        messages.success(request, f'Paket {package["miles"]} miles berhasil dibeli!')
        
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return redirect('blue:package_list')


# ===== TIER INFORMATION (Member) =====

@login_required_member
def tier_info(request):
    """R — Display tier information and benefits."""
    member = get_member(request)
    
    # Fetch tier information
    sql = """
        SELECT 
            id_tier,
            nama as tier_name,
            minimal_frekuensi_terbang,
            minimal_tier_miles
        FROM TIER
        ORDER BY minimal_tier_miles ASC
    """
    
    tiers = execute_raw_sql(sql)
    
    # Get current member tier
    sql_member_tier = """
        SELECT t.id_tier, t.nama as tier_name
        FROM TIER t
        WHERE t.id_tier = %s
    """
    
    current_tier_list = execute_raw_sql(sql_member_tier, [member.id_tier_id])
    current_tier = current_tier_list[0] if current_tier_list else None
    
    context = {
        'member': member,
        'tiers': tiers,
        'current_tier': current_tier,
        'navbar_type': 'member',
    }
    return render(request, 'hadiah/tier.html', context)


# ===== REPORTS & TRANSACTION HISTORY (Staff) =====

@login_required_staff
def report_view(request):
    """RD — Display miles transaction reports and history."""
    staf = get_staf(request)
    
    # Filter parameters
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    transaction_type = request.GET.get('type', 'semua')  # redeem, transfer, buy, claim
    
    # Base query for transactions
    sql = """
        SELECT 
            'Redeem' as tipe,
            email_member,
            kode_hadiah as reference,
            -harga_miles as miles,
            tanggal_redeem as tanggal
        FROM RIWAYAT_REDEEM
        WHERE 1=1
    """
    
    params = []
    
    if transaction_type in ['redeem', 'semua']:
        if start_date:
            sql += " AND tanggal_redeem >= %s"
            params.append(start_date)
        if end_date:
            sql += " AND tanggal_redeem <= %s"
            params.append(end_date)
    
    # Add transfer transactions
    if transaction_type in ['transfer', 'semua']:
        sql += """
            UNION ALL
            SELECT 
                'Transfer Keluar' as tipe,
                email_member_1 as email_member,
                email_member_2 as reference,
                -jumlah as miles,
                timestamp as tanggal
            FROM TRANSFER
            WHERE 1=1
        """
        if start_date:
            sql += " AND timestamp >= %s"
            params.append(start_date) if not (transaction_type in ['redeem'] and start_date in params) else None
        if end_date:
            sql += " AND timestamp <= %s"
            params.append(end_date) if not (transaction_type in ['redeem'] and end_date in params) else None
    
    sql += " ORDER BY tanggal DESC LIMIT 500"
    
    transactions = execute_raw_sql(sql, params) if params else execute_raw_sql(sql)
    
    # Calculate summary statistics
    sql_summary = """
        SELECT 
            COUNT(*) as total_transactions,
            SUM(CASE WHEN tanggal_redeem IS NOT NULL THEN 1 ELSE 0 END) as total_redeems
        FROM RIWAYAT_REDEEM
    """
    
    summary_list = execute_raw_sql(sql_summary)
    summary = summary_list[0] if summary_list else {'total_transactions': 0, 'total_redeems': 0}
    
    context = {
        'staf': staf,
        'transactions': transactions,
        'summary': summary,
        'start_date': start_date,
        'end_date': end_date,
        'transaction_type': transaction_type,
        'navbar_type': 'staff',
    }
    return render(request, 'transfer/report.html', context)