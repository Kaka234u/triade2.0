"""Infraestrutura compartilhada da VORTEX 7.

Concentra o que é usado tanto pela loja (routes.py) quanto pelo painel
administrativo (admin.py): conexão com o banco, tabelas de pedidos,
configurações da loja, proteção CSRF e autenticação do admin.
"""

import hmac
import os
import re
import secrets
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse

from flask import abort, flash, g, redirect, request, session, url_for
from markupsafe import Markup
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("VORTEX7_DB", os.path.join(BASE_DIR, "database.db"))
PRODUCT_IMG_DIR = os.path.join(BASE_DIR, "static", "images", "products")
PHOTO_EXTS = ("webp", "jpg", "jpeg", "png", "avif")

# Horário de Brasília (UTC-3, sem horário de verão desde 2019).
BRT = timezone(timedelta(hours=-3))


# ---------------------------------------------------------------------------
# Datas
# ---------------------------------------------------------------------------

def now_iso():
    """Timestamp UTC em ISO-8601 (é assim que tudo é gravado no banco)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def to_brt(iso_value):
    if not iso_value:
        return None
    try:
        dt = datetime.fromisoformat(iso_value)
    except ValueError:
        return None
    if dt.tzinfo is None:  # registros antigos (utcnow sem tz)
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BRT)


def fmt_datetime(iso_value, with_time=True):
    dt = to_brt(iso_value)
    if not dt:
        return "—"
    return dt.strftime("%d/%m/%Y %H:%M" if with_time else "%d/%m/%Y")


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    user_id INTEGER,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    customer_phone TEXT,
    customer_cpf TEXT,
    ship_cep TEXT,
    ship_address TEXT,
    ship_complement TEXT,
    ship_neighborhood TEXT,
    ship_city TEXT,
    ship_state TEXT,
    shipping_method TEXT NOT NULL,
    shipping_days INTEGER,
    subtotal REAL NOT NULL,
    shipping_price REAL NOT NULL DEFAULT 0,
    discount REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL,
    payment_method TEXT NOT NULL,
    payment_status TEXT NOT NULL DEFAULT 'pendente',
    status TEXT NOT NULL DEFAULT 'aguardando_pagamento',
    pix_payload TEXT,
    mp_preference_id TEXT,
    mp_init_point TEXT,
    mp_payment_id TEXT,
    tracking_code TEXT,
    customer_notes TEXT,
    admin_notes TEXT,
    created_at TEXT NOT NULL,
    paid_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER,
    name TEXT NOT NULL,
    size TEXT,
    color TEXT,
    qty INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    line_total REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id);

CREATE TABLE IF NOT EXISTS order_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    actor TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_events_order ON order_events(order_id);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact TEXT,
    subject TEXT,
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
"""

# Valores iniciais das configurações (só são gravados se a chave não existir).
DEFAULT_SETTINGS = {
    # Dados da loja (aparecem no comprovante)
    "store_name": "VORTEX 7",
    "store_legal_name": "",
    "store_cnpj": "",
    "store_email": "contato@vortex7.com.br",
    "store_phone": "(85) 3000-0007",
    "store_whatsapp": "",
    "store_address": "",
    # Pagamentos
    "test_mode": "1",              # 1 = modo teste (pagamentos simulados)
    "pix_key": "",
    "pix_receiver_name": "VORTEX 7",
    "pix_city": "FORTALEZA",
    "pix_discount_percent": "5",
    "mp_access_token": "",         # Mercado Pago (cartão e boleto)
    "public_base_url": "",         # ex.: https://minhaloja.com.br
}


def ensure_schema(conn):
    conn.executescript(SCHEMA)
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()


def ensure_admin(conn):
    """Cria o primeiro admin se a tabela estiver vazia.

    A senha vem de ADMIN_PASSWORD; se não existir, uma senha aleatória é
    gerada e mostrada UMA vez no console/log de inicialização.
    """
    if conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0]:
        return
    email = os.environ.get("ADMIN_EMAIL", "admin@vortex7.com.br").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD")
    generated = not password
    if generated:
        password = secrets.token_urlsafe(9)
    conn.execute(
        "INSERT INTO admins (name, email, password, created_at) VALUES (?, ?, ?, ?)",
        ("Administrador", email, generate_password_hash(password), now_iso()),
    )
    conn.commit()
    if generated:
        print("\n" + "=" * 62)
        print("  VORTEX 7 — PAINEL ADMIN CRIADO")
        print(f"  URL:    /vortex7/admin")
        print(f"  E-mail: {email}")
        print(f"  Senha:  {password}")
        print("  (anote agora: ela não será mostrada de novo.)")
        print("  Para trocar/resetar: python vortex7/criar_admin.py")
        print("=" * 62 + "\n")


# ---------------------------------------------------------------------------
# Configurações da loja
# ---------------------------------------------------------------------------

def load_settings(db=None):
    db = db or get_db()
    data = dict(DEFAULT_SETTINGS)
    for row in db.execute("SELECT key, value FROM settings"):
        data[row["key"]] = row["value"]
    return data


def save_setting(db, key, value):
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def format_brl(value):
    value = float(value or 0)
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def only_digits(text):
    return "".join(ch for ch in (text or "") if ch.isdigit())


def slugify(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "item"


def safe_next_url(target, fallback):
    """Aceita apenas caminhos relativos do próprio site (evita open redirect)."""
    if not target:
        return fallback
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return fallback
    return target


def valid_cpf(cpf):
    cpf = only_digits(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for length in (9, 10):
        total = sum(int(cpf[i]) * (length + 1 - i) for i in range(length))
        digit = (total * 10) % 11 % 10
        if digit != int(cpf[length]):
            return False
    return True


def external_url(endpoint, settings=None, **values):
    """URL absoluta; usa 'public_base_url' das configurações se existir."""
    base = ((settings or {}).get("public_base_url") or "").strip().rstrip("/")
    if base:
        return base + url_for(endpoint, **values)
    return url_for(endpoint, _external=True, **values)


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

CSRF_EXEMPT_ENDPOINTS = {"vortex7.webhook_mercadopago"}


def csrf_token():
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(24)
        session["_csrf"] = token
    return token


def csrf_input():
    return Markup(f'<input type="hidden" name="csrf_token" value="{csrf_token()}">')


def verify_csrf():
    """before_request: bloqueia POSTs sem token válido."""
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    if request.endpoint in CSRF_EXEMPT_ENDPOINTS:
        return None
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
    expected = session.get("_csrf", "")
    if not sent or not expected or not hmac.compare_digest(sent, expected):
        flash("Sua sessão expirou. Tente novamente.", "error")
        return redirect(request.referrer or url_for("vortex7.index"))
    return None


# ---------------------------------------------------------------------------
# Autenticação do admin
# ---------------------------------------------------------------------------

ADMIN_SESSION_HOURS = 8


def current_admin():
    if "admin_row" in g:
        return g.admin_row
    admin = None
    admin_id = session.get("admin_id")
    started = session.get("admin_at")
    if admin_id and started:
        try:
            fresh = datetime.now(timezone.utc) - datetime.fromisoformat(started) < timedelta(hours=ADMIN_SESSION_HOURS)
        except ValueError:
            fresh = False
        if fresh:
            admin = get_db().execute("SELECT * FROM admins WHERE id = ?", (admin_id,)).fetchone()
        if not admin:
            session.pop("admin_id", None)
            session.pop("admin_at", None)
    g.admin_row = admin
    return admin


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_admin():
            flash("Faça login para acessar o painel.", "error")
            return redirect(url_for("vortex7.admin.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped


def is_admin_session():
    return current_admin() is not None
