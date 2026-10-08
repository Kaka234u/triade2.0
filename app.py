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

from customer_portal import register_portal, init_portal
from kaka.routes import get_db as kaka_connection
from sectest.routes import get_db as sectest_connection
register_portal(app, 'kaka', kaka_prefix, kaka_connection)
if mode == 'triade':
    register_portal(app, 'sectest', '/sectest', sectest_connection)

from finance import register_finance, init_finance
from client_payments import register_payments, init_payments
from sectest_plans import register_plans, init_plans
register_finance(app,'kaka',kaka_prefix,kaka_connection)
register_payments(app,'kaka',kaka_prefix,kaka_connection)
if mode=='triade':
    register_finance(app,'sectest','/sectest',sectest_connection)
    register_payments(app,'sectest','/sectest',sectest_connection)
    register_plans(app,sectest_connection)
app.jinja_env.globals['finance_ready']=True
from notifications import init_notifications, register_notifications
from brand_ui import init_brand_ui
register_notifications(app,'kaka',kaka_prefix,kaka_connection)
if mode=='triade':
    register_notifications(app,'sectest','/sectest',sectest_connection)
init_brand_ui(app, ['kaka','sectest'] if mode=='triade' else ['kaka'])

with app.app_context():
    init_accounts(app)
    kaka_init_db()
    init_portal(kaka_connection())
    init_finance(kaka_connection())
    init_payments(kaka_connection())
    init_notifications(kaka_connection())
    kaka_connection().commit()
    if mode == 'triade':
        vortex7_init_db()
        sectest_init_db()
        init_portal(sectest_connection())
        init_finance(sectest_connection())
        init_payments(sectest_connection())
        init_notifications(sectest_connection())
        init_plans(sectest_connection())
        sectest_connection().commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)),
            debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
