"""Tríade: Vortex7, FK Káka Autodetail e SecTest no mesmo servidor."""
import os
import secrets
from datetime import timedelta
from pathlib import Path
from flask import Flask, render_template
from accounts import init_accounts, register_accounts
from vortex7.routes import app as vortex7_bp, init_db as vortex7_init_db
from kaka.routes import app as kaka_bp, init_db as kaka_init_db
from sectest.routes import app as sectest_bp, init_db as sectest_init_db

app = Flask(__name__, static_url_path='/shared-static')
secret_file = Path(__file__).with_name('.session-secret')
secret = os.environ.get('SECRET_KEY')
if not secret:
    try:
        with secret_file.open('x', encoding='utf-8') as stream:
            stream.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    secret = secret_file.read_text(encoding='utf-8').strip()
app.secret_key = secret
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1',
                  PERMANENT_SESSION_LIFETIME=timedelta(hours=2), MAX_CONTENT_LENGTH=8*1024*1024)
mode = os.environ.get('SITE_MODE', 'triade')
if mode not in {'triade', 'kaka'}:
    raise RuntimeError('SITE_MODE deve ser triade ou kaka')
kaka_prefix = '' if mode == 'kaka' else '/kaka'
app.register_blueprint(kaka_bp, url_prefix=kaka_prefix)
register_accounts(app, 'kaka', kaka_prefix)
if mode == 'triade':
    app.register_blueprint(vortex7_bp, url_prefix='/vortex7')
    app.register_blueprint(sectest_bp, url_prefix='/sectest')
    register_accounts(app, 'sectest', '/sectest')

    @app.route('/')
    def portal_home():
        return render_template('portal/index.html')

with app.app_context():
    init_accounts(app)
    kaka_init_db()
    if mode == 'triade':
        vortex7_init_db()
        sectest_init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)),
            debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
