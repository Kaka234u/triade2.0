"""Contas isoladas por marca, sessões de servidor e proteção dos formulários."""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from functools import wraps
from pathlib import Path

import click
from flask import Blueprint, abort, current_app, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
AUTH_DB = Path(os.environ.get('TRIADE_AUTH_DB', ROOT / 'accounts.db'))
BRANDS = {'kaka': 'FK Káka Autodetail', 'sectest': 'SecTest'}

def db():
    if 'accounts_db' not in g:
        g.accounts_db = sqlite3.connect(AUTH_DB)
        g.accounts_db.row_factory = sqlite3.Row
    return g.accounts_db

def csrf_token():
    if 'brand_csrf' not in session:
        session['brand_csrf'] = secrets.token_urlsafe(32)
    return session['brand_csrf']

def verify_csrf():
    token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
    if not token or not hmac.compare_digest(str(token), str(session.get('brand_csrf', ''))):
        abort(400, 'Sessão do formulário expirada. Atualize a página e tente novamente.')

def current_user(brand, admin=False):
    key = f'{brand}_' + ('admin_session' if admin else 'user_session')
    token = session.get(key)
    if not token:
        return None
    row = db().execute('''SELECT u.* FROM accounts u JOIN account_sessions s ON s.user_id=u.id
        WHERE s.token=? AND s.expires>? AND u.brand=?''',
        (hashlib.sha256(token.encode()).hexdigest(), time.time(), brand)).fetchone()
    return row if row and (not admin or row['role'] == 'admin') else None

def login_user(brand, user, admin=False):
    logout_user(brand, admin)
    token = secrets.token_urlsafe(32)
    db().execute('INSERT INTO account_sessions VALUES (?,?,?)',
                 (hashlib.sha256(token.encode()).hexdigest(), user['id'], time.time()+7200))
    db().commit()
    session[f'{brand}_' + ('admin_session' if admin else 'user_session')] = token
    session.permanent = True

def logout_user(brand, admin=False):
    token = session.pop(f'{brand}_' + ('admin_session' if admin else 'user_session'), None)
    if token:
        db().execute('DELETE FROM account_sessions WHERE token=?', (hashlib.sha256(token.encode()).hexdigest(),))
        db().commit()

def authenticate(brand, identity, password, admin=False):
    # Limite persistente por origem e conta; não depende de memória de um worker.
    identity = str(identity or '').strip().lower()[:254]
    password = str(password or '')
    origin = request.remote_addr or 'local'
    keys = [f'{brand}:ip:{origin}', f'{brand}:account:{identity}']
    now = time.time()
    conn = db()
    conn.execute('DELETE FROM login_attempts WHERE created<?', (now-900,))
    for key in keys:
        count = conn.execute('SELECT count(*) FROM login_attempts WHERE bucket=?', (key,)).fetchone()[0]
        if count >= (40 if ':ip:' in key else 10):
            conn.commit()
            return None, 'Muitas tentativas. Aguarde 15 minutos.', 429
    user = conn.execute('SELECT * FROM accounts WHERE brand=? AND email=?', (brand, identity)).fetchone()
    valid = len(password) <= 256 and check_password_hash(user['password_hash'] if user else current_app.config['DUMMY_PASSWORD_HASH'], password)
    if not user or not valid or (admin and user['role'] != 'admin'):
        conn.executemany('INSERT INTO login_attempts VALUES (?,?)', [(key, now) for key in keys])
        conn.commit()
        return None, 'E-mail ou senha inválidos.', 401
    conn.execute('DELETE FROM login_attempts WHERE bucket=?', (keys[1],))
    conn.commit()
    login_user(brand, user, admin)
    return user, None, 200

def require_admin(brand):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user(brand, True):
                if request.is_json or '/api/' in request.path:
                    return jsonify(error='Acesso administrativo necessário.'), 401
                return redirect(url_for(f'{brand}_accounts.admin_login'))
            if request.method == 'POST':
                verify_csrf()
            return view(*args, **kwargs)
        return wrapped
    return decorator

def register_accounts(app, brand, prefix):
    bp = Blueprint(f'{brand}_accounts', __name__)
    @bp.after_request
    def private_headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    def page(mode, **kwargs):
        return render_template('accounts/form.html', mode=mode, brand=brand, brand_name=BRANDS[brand], **kwargs)

    @bp.route('/login', methods=['GET', 'POST'])
    def login():
        error = None
        status = 200
        if request.method == 'POST':
            verify_csrf()
            user, error, status = authenticate(brand, request.form.get('email'), request.form.get('password'))
            if user:
                return redirect(url_for(f'{brand}_accounts.account'))
        return page('login', error=error), status

    @bp.route('/criar-conta', methods=['GET', 'POST'])
    def register():
        error = None
        if request.method == 'POST':
            verify_csrf()
            name = request.form.get('name', '').strip()[:120]
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            if not name or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email)>254:
                error = 'Informe seu nome e um e-mail válido.'
            elif not 10 <= len(password) <= 256:
                error = 'Use uma senha entre 10 e 256 caracteres.'
            elif password != request.form.get('confirm_password'):
                error = 'As senhas não coincidem.'
            else:
                try:
                    db().execute('INSERT INTO accounts (brand,name,email,password_hash,role) VALUES (?,?,?,?,?)',
                        (brand, name, email, generate_password_hash(password), 'customer'))
                    db().commit()
                    return redirect(url_for(f'{brand}_accounts.login', created=1))
                except sqlite3.IntegrityError:
                    db().rollback()
                    error = 'Não foi possível criar esta conta. Confira o e-mail ou entre com sua conta existente.'
        return page('register', error=error), 400 if error else 200

    @bp.route('/conta')
    def account():
        user = current_user(brand)
        if not user:
            return redirect(url_for(f'{brand}_accounts.login'))
        return redirect(url_for(brand + '_portal.index'))

    @bp.post('/logout')
    def logout():
        verify_csrf()
        logout_user(brand)
        return redirect(url_for(f'{brand}_accounts.login'))

    @bp.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        error = None
        status = 200
        if current_user(brand, True):
            return redirect(url_for(f'{brand}.admin_dashboard'))
        if request.method == 'POST':
            verify_csrf()
            user, error, status = authenticate(brand, request.form.get('email'), request.form.get('password'), True)
            if user:
                return redirect(url_for(f'{brand}.admin_dashboard'))
        return page('admin', error=error), status

    @bp.post('/admin/logout')
    def admin_logout():
        verify_csrf()
        logout_user(brand, True)
        return redirect(url_for(f'{brand}_accounts.admin_login'))

    app.register_blueprint(bp, url_prefix=prefix)

def init_accounts(app):
    AUTH_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(AUTH_DB) as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY, brand TEXT NOT NULL,
          name TEXT NOT NULL, email TEXT NOT NULL, password_hash TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'customer', UNIQUE(brand,email));
        CREATE TABLE IF NOT EXISTS account_sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts (bucket TEXT NOT NULL, created REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS attempt_bucket ON login_attempts(bucket,created);
        ''')
    app.config['DUMMY_PASSWORD_HASH'] = generate_password_hash(secrets.token_urlsafe(32))
    app.jinja_env.globals.update(brand_csrf=csrf_token, brand_user=current_user)

    @app.teardown_appcontext
    def close_accounts(error=None):
        conn = g.pop('accounts_db', None)
        if conn is not None:
            conn.close()

    @app.cli.command('criar-admin')
    @click.option('--marca', type=click.Choice(list(BRANDS)), required=True)
    @click.option('--email', prompt=True)
    @click.password_option(confirmation_prompt=True)
    def create_admin(marca, email, password):
        """Cria ou atualiza uma conta administrativa sem senha padrão."""
        if len(password)<10 or len(password)>256:
            raise click.ClickException('A senha deve ter entre 10 e 256 caracteres.')
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            raise click.ClickException('Informe um e-mail válido.')
        db().execute('''INSERT INTO accounts (brand,name,email,password_hash,role) VALUES (?,?,?,?, 'admin')
          ON CONFLICT(brand,email) DO UPDATE SET password_hash=excluded.password_hash,role='admin' ''',
          (marca, 'Administrador', email.strip().lower(), generate_password_hash(password)))
        db().execute('DELETE FROM account_sessions WHERE user_id IN (SELECT id FROM accounts WHERE brand=? AND email=?)', (marca,email.strip().lower()))
        db().commit()
        click.echo('Administrador salvo. Entre pelo endereço /admin da marca.')
