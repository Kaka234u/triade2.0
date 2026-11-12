"""Sandbox FK por administrador. Nunca usa bancos, arquivos ou provedores reais."""
import sqlite3
from pathlib import Path
from flask import abort, current_app, has_request_context, redirect, render_template, request, session, url_for
from accounts import current_user, require_admin


def active():
    if not has_request_context() or not session.get('kaka_demo_owner'):
        return False
    admin = current_user('kaka', True)
    return bool(admin and session['kaka_demo_owner'] == admin['id'])


def database_path():
    if not active():
        return None
    root = Path(current_app.config.get('FK_DEMO_DIR', Path(current_app.instance_path) / 'fk-demo'))
    root.mkdir(parents=True, exist_ok=True)
    return root / ('admin-' + str(int(session['kaka_demo_owner'])) + '.db')


def initialize(path):
    from .routes import init_db
    from customer_portal import init_portal
    from finance import init_finance
    from client_payments import init_payments
    from notifications import init_notifications
    init_db(path)
    with sqlite3.connect(path) as conn:
        init_portal(conn)
        init_finance(conn)
        init_payments(conn)
        init_notifications(conn)
        conn.execute('CREATE TABLE IF NOT EXISTS demo_events (id INTEGER PRIMARY KEY, invoice_id INTEGER, outcome TEXT, created_at TEXT DEFAULT (datetime(\'now\')))')


def simulate(conn, ident, action):
    """Serialize repeated submissions; approval only credits the remaining balance."""
    from datetime import date
    from finance import invoice_rows
    import secrets
    if not active():
        abort(403)
    conn.execute('BEGIN IMMEDIATE')
    try:
        row = next((r for r in invoice_rows(conn) if r['id'] == ident), None)
        if not row or row['owner_id'] != session['kaka_demo_owner']:
            abort(404)
        if row['canceled']:
            abort(400, 'Esta cobrança foi cancelada.')
        if action == 'simulate_paid':
            if row['balance']:
                conn.execute('INSERT INTO receipts(invoice_id,amount,method,paid_on,actor,reference) VALUES (?,?,?,?,?,?)',
                    (ident,row['balance'],'demonstracao',date.today().isoformat(),'Simulador FK','demo:'+secrets.token_hex(16)))
        elif action == 'simulate_refund':
            conn.execute('UPDATE receipts SET reversed=1 WHERE invoice_id=? AND reversed=0', (ident,))
        elif action not in {'simulate_pending', 'simulate_declined'}:
            abort(400)
        elif row['paid']:
            abort(400, 'Estorne o pagamento antes de testar outro resultado.')
        conn.execute('INSERT INTO demo_events(invoice_id,outcome) VALUES (?,?)', (ident,action))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def register_demo(app, prefix):
    from flask import Blueprint
    bp = Blueprint('kaka_demo', __name__)
    app.jinja_env.globals['fk_demo_active'] = active

    @bp.route('/admin/testes', methods=['GET','POST'])
    @require_admin('kaka')
    def index():
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'start':
                session['kaka_demo_owner'] = current_user('kaka', True)['id']
                initialize(database_path())
                return redirect(url_for('kaka_demo.index'))
            if action == 'stop':
                session.pop('kaka_demo_owner', None)
                return redirect(url_for('kaka.admin_dashboard'))
            if action == 'reset' and active():
                # Delete records only in this administrator's isolated database.
                # Keep the schema and avoid touching any uploads or production DB.
                with sqlite3.connect(database_path()) as conn:
                    for table in ('notification_reads','notifications','demo_events','payment_attempts','receipts','invoices','client_messages','client_requests','booking_requests','quote_requests'):
                        conn.execute('DELETE FROM ' + table)
                return redirect(url_for('kaka_demo.index', reset=1))
            abort(400)
        return render_template('kaka/admin/demo.html', title='Modo de testes')

    app.register_blueprint(bp, url_prefix=prefix)

    @app.before_request
    def protect_demo():
        if not active() or not (request.endpoint or '').startswith(('kaka.', 'kaka_')):
            return
        # Demo content writes could otherwise create shared uploaded files.
        if request.method == 'POST' and request.endpoint in {'kaka.admin_images','kaka.admin_settings','kaka.admin_services','kaka.admin_save_content'}:
            abort(400, 'No modo de testes, use apenas os fluxos de atendimento e faturamento. Saia do modo para editar o site.')

    @app.after_request
    def banner(response):
        if not active() or not (request.endpoint or '').startswith(('kaka.', 'kaka_')):
            return response
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        if response.mimetype == 'text/html' and response.status_code == 200:
            html = response.get_data(as_text=True)
            html = html.replace('</body>', render_template('kaka/demo_banner.html') + '</body>')
            response.set_data(html)
        return response
