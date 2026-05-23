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
        if name == 'id_tier_id' and 'id_tier' in self:
            return self['id_tier']
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


def get_member(request):
    email = request.session.get('email')
    role = request.session.get('role')

    if not email or role != 'member':
        return None

    rows = execute_raw_sql(
        """
        SELECT m.email, m.nomor_member, m.tanggal_bergabung, m.id_tier,
               m.award_miles, m.total_miles,
               p.first_mid_name, p.last_name, p.salutation,
               p.country_code, p.mobile_number,
               p.tanggal_lahir, p.kewarganegaraan,
               m.email AS email_id
        FROM member m
        JOIN pengguna p ON m.email = p.email
        WHERE m.email = %s
        """,
        [email],
    )
    return rows[0] if rows else None


def get_staf(request):
    email = request.session.get('email')
    role = request.session.get('role')

    if not email or role != 'staff':
        return None

    rows = execute_raw_sql(
        """
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
        """,
        [email],
    )
    return rows[0] if rows else None


def login_required_member(view_func):
    def wrapper(request, *args, **kwargs):
        if not get_member(request):
            messages.error(request, 'Silakan login sebagai Member terlebih dahulu.')
            return redirect('main:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def login_required_staff(view_func):
    def wrapper(request, *args, **kwargs):
        if not get_staf(request):
            messages.error(request, 'Silakan login sebagai Staff terlebih dahulu.')
            return redirect('main:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def provider_name(row):
    return row.get('nama_mitra') or row.get('nama_maskapai') or f"Penyedia {row.get('id_penyedia')}"


@login_required_member
def redeem_hadiah(request):
    member = get_member(request)
    tab = request.GET.get('tab', 'katalog')

    rewards = execute_raw_sql(
        """
        SELECT h.kode_hadiah AS code, h.kode_hadiah,
               h.nama AS name, h.nama AS nama_hadiah,
               h.miles, h.miles AS harga_miles,
               h.deskripsi AS desc, h.deskripsi,
               h.valid_start_date, h.program_end, h.id_penyedia,
               mt.nama_mitra, mk.nama_maskapai
        FROM hadiah h
        LEFT JOIN mitra mt ON mt.id_penyedia = h.id_penyedia
        LEFT JOIN maskapai mk ON mk.id_penyedia = h.id_penyedia
        WHERE h.valid_start_date <= CURRENT_DATE AND h.program_end >= CURRENT_DATE
        ORDER BY h.valid_start_date DESC
        """
    )
    for reward in rewards:
        reward['partner'] = provider_name(reward)
        reward['period'] = f"{reward.get('valid_start_date')} - {reward.get('program_end')}"

    history = execute_raw_sql(
        """
        SELECT r.kode_hadiah,
               h.nama AS name,
               r.timestamp AS date,
               h.miles AS miles
        FROM redeem r
        JOIN hadiah h ON r.kode_hadiah = h.kode_hadiah
        WHERE r.email_member = %s
        ORDER BY r.timestamp DESC
        LIMIT 20
        """,
        [member.email_id],
    )

    return render(request, 'hadiah/redeem_hadiah.html', {
        'member': member,
        'tab': tab,
        'rewards': rewards,
        'history': history,
        'user_miles': member.award_miles,
        'navbar_type': 'member',
    })


@login_required_member
@require_http_methods(["POST"])
def redeem_confirm(request):
    member = get_member(request)
    kode_hadiah = request.POST.get('kode_hadiah', '').strip()

    if not kode_hadiah:
        messages.error(request, 'Kode hadiah tidak valid.')
        return redirect('blue:redeem_hadiah')

    rows = execute_raw_sql(
        "SELECT kode_hadiah, nama, miles FROM hadiah WHERE kode_hadiah = %s",
        [kode_hadiah],
    )
    if not rows:
        messages.error(request, 'Hadiah tidak ditemukan.')
        return redirect('blue:redeem_hadiah')

    hadiah = rows[0]
    miles = hadiah.miles

    if member.award_miles < miles:
        messages.error(request, f'Award miles Anda tidak mencukupi. Diperlukan: {miles}, Tersedia: {member.award_miles}')
        return redirect('blue:redeem_hadiah')

    try:
        execute_raw_sql_update(
            """
            INSERT INTO redeem (email_member, kode_hadiah, timestamp, status)
            VALUES (%s, %s, %s, %s)
            """,
            [member.email_id, kode_hadiah, timezone.now(), 'Berhasil'],
        )
        execute_raw_sql_update(
            "UPDATE member SET award_miles = award_miles - %s WHERE email = %s",
            [miles, member.email_id],
        )
        messages.success(request, f'Hadiah berhasil ditukar. {miles} award miles dikurangi dari akun Anda.')
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')

    return redirect('blue:redeem_hadiah')


def default_packages():
    return [
        {'code': 'AMP-001', 'miles': 1000, 'price': 150000},
        {'code': 'AMP-002', 'miles': 5000, 'price': 650000},
        {'code': 'AMP-003', 'miles': 10000, 'price': 1200000},
        {'code': 'AMP-004', 'miles': 25000, 'price': 2750000},
    ]


@login_required_member
def package_list(request):
    member = get_member(request)
    packages = execute_raw_sql(
        """
        SELECT id_package AS code, jumlah_miles AS miles, harga AS price
        FROM award_miles_package
        ORDER BY jumlah_miles
        """
    ) or default_packages()

    return render(request, 'hadiah/package_list.html', {
        'member': member,
        'packages': packages,
        'current_miles': member.award_miles,
        'user_miles': member.award_miles,
        'navbar_type': 'member',
    })


@login_required_member
@require_http_methods(["POST"])
def buy_package(request):
    member = get_member(request)
    kode_package = request.POST.get('kode_package', '').strip()

    packages = {package['code']: package for package in default_packages()}
    db_packages = execute_raw_sql(
        "SELECT id_package AS code, jumlah_miles AS miles FROM award_miles_package"
    )
    for package in db_packages:
        packages[package.code] = package

    if kode_package not in packages:
        messages.error(request, 'Paket tidak valid.')
        return redirect('blue:package_list')

    try:
        execute_raw_sql_update(
            """
            INSERT INTO member_award_miles_package (email_member, id_package, timestamp)
            VALUES (%s, %s, %s)
            """,
            [member.email_id, kode_package, timezone.now()],
        )
        messages.success(request, f'Paket {packages[kode_package]["miles"]} miles berhasil dibeli!')
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')

    return redirect('blue:package_list')


@login_required_member
def tier_info(request):
    member = get_member(request)
    rows = execute_raw_sql(
        """
        SELECT id_tier, nama, minimal_frekuensi_terbang, minimal_tier_miles
        FROM tier
        ORDER BY minimal_tier_miles ASC
        """
    )

    tiers = []
    next_tier = None
    for row in rows:
        tier = DBRow({
            'id': row.id_tier,
            'name': row.nama,
            'min_flight': row.minimal_frekuensi_terbang,
            'min_miles': row.minimal_tier_miles,
            'benefits': [
                'Prioritas layanan member',
                'Akses promo sesuai tier',
                'Akumulasi miles lebih mudah dipantau',
            ],
        })
        tiers.append(tier)
        if not next_tier and row.minimal_tier_miles > member.total_miles:
            next_tier = tier

    current_tier = next((tier.name for tier in tiers if tier.id == member.id_tier_id), member.id_tier_id)

    return render(request, 'hadiah/tier.html', {
        'member': member,
        'tiers': tiers,
        'current_tier': current_tier,
        'current_miles': member.total_miles,
        'next_tier': next_tier,
        'navbar_type': 'member',
    })


@login_required_staff
def report_view(request):
    staf = get_staf(request)
    tab = request.GET.get('tab', 'riwayat')

    transactions = execute_raw_sql(
        """
        SELECT 'Redeem' AS type,
               p.first_mid_name || ' ' || p.last_name AS user,
               r.email_member AS email,
               -h.miles AS miles,
               r.timestamp AS date
        FROM redeem r
        JOIN hadiah h ON r.kode_hadiah = h.kode_hadiah
        JOIN pengguna p ON r.email_member = p.email
        UNION ALL
        SELECT 'Transfer' AS type,
               p.first_mid_name || ' ' || p.last_name AS user,
               t.email_member_1 AS email,
               -t.jumlah AS miles,
               t.timestamp AS date
        FROM transfer t
        JOIN pengguna p ON t.email_member_1 = p.email
        UNION ALL
        SELECT 'Package' AS type,
               p.first_mid_name || ' ' || p.last_name AS user,
               mp.email_member AS email,
               amp.jumlah_miles AS miles,
               mp.timestamp AS date
        FROM member_award_miles_package mp
        JOIN award_miles_package amp ON mp.id_package = amp.id_package
        JOIN pengguna p ON mp.email_member = p.email
        ORDER BY date DESC
        LIMIT 500
        """
    )

    total_miles = execute_raw_sql("SELECT COALESCE(SUM(total_miles), 0) AS value FROM member")
    redeem_count = execute_raw_sql("SELECT COUNT(*) AS value FROM redeem")
    klaim_count = execute_raw_sql(
        "SELECT COUNT(*) AS value FROM claim_missing_miles WHERE status_penerimaan = %s",
        ['Disetujui'],
    )
    top_members = execute_raw_sql(
        """
        SELECT p.first_mid_name || ' ' || p.last_name AS name,
               m.total_miles AS total
        FROM member m
        JOIN pengguna p ON m.email = p.email
        ORDER BY m.total_miles DESC
        LIMIT 10
        """
    )

    summary = DBRow({
        'total_miles': total_miles[0].value if total_miles else 0,
        'redeem': redeem_count[0].value if redeem_count else 0,
        'klaim': klaim_count[0].value if klaim_count else 0,
    })

    return render(request, 'transfer/report.html', {
        'staf': staf,
        'tab': tab,
        'transactions': transactions,
        'summary': summary,
        'top_members': top_members,
        'navbar_type': 'staff',
    })
