from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import IntegrityError
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.conf import settings
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from urllib.parse import urlparse

from modules.green.models import (
    Member, Staf, Maskapai, Bandara,
    ClaimMissingMiles, Pengguna, Transfer
)


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
        # For SQLite in development, we'll use Django's connection
        from django.db import connection
        return connection
    return conn


def execute_raw_sql(sql, params=None):
    """Execute raw SQL query and return results."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        
        results = cursor.fetchall()
        cursor.close()
        if hasattr(conn, 'commit'):
            conn.commit()
        conn.close()
        
        return [dict(row) for row in results] if results else []
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
        conn.close()
        
        return rowcount
    except Exception as e:
        print(f"Database error: {e}")
        return 0


# Helper

def get_member(request):
    """Return Member object for the logged-in user, or None."""
    email = request.session.get('email')
    if not email:
        return None
    try:
        return Member.objects.select_related('email', 'id_tier').get(email=email)
    except Member.DoesNotExist:
        return None


def get_staf(request):
    """Return Staf object for the logged-in user, or None."""
    email = request.session.get('email')
    if not email:
        return None
    try:
        return Staf.objects.select_related('email', 'kode_maskapai').get(email=email)
    except Staf.DoesNotExist:
        return None


def login_required_member(view_func):
    """Decorator: redirect to login if not a Member."""
    def wrapper(request, *args, **kwargs):
        if not get_member(request):
            messages.error(request, 'Silakan login sebagai Member terlebih dahulu.')
            return redirect('main:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def login_required_staf(view_func):
    """Decorator: redirect to login if not Staf."""
    def wrapper(request, *args, **kwargs):
        if not get_staf(request):
            messages.error(request, 'Silakan login sebagai Staf terlebih dahulu.')
            return redirect('main:login')
        return view_func(request, *args, **kwargs)
    return wrapper
