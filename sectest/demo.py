"""Demonstração de atendimento da SecTest, isolada por administrador."""
import sqlite3
from pathlib import Path
from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for
from accounts import current_user, require_admin
from kaka.demo import active

bp = Blueprint('sectest_demo', __name__)

def database_path():
    if not active('sectest'):
        return None
    root = Path(current_app.instance_path) / 'sectest-demo'
    root.mkdir(parents=True, exist_ok=True)
    return root / f"admin-{int(session['sectest_demo_owner'])}.db"

def initialize(path):
    from .routes import init_db
    from customer_portal import init_portal
    from finance import init_finance
    from client_payments import init_payments
    from notifications import init_notifications
    from sectest_plans import init_plans
    init_db(path)
    with sqlite3.connect(path) as conn:
        for init in (init_portal, init_finance, init_payments, init_notifications, init_plans):
            init(conn)
        conn.execute("""CREATE TABLE IF NOT EXISTS demo_events (
            id INTEGER PRIMARY KEY, invoice_id INTEGER, outcome TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

@bp.route('/admin/testes', methods=['GET', 'POST'])
@require_admin('sectest')
def index():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'start':
            session['sectest_demo_owner'] = current_user('sectest', True)['id']
            initialize(database_path())
        elif action == 'stop':
            session.pop('sectest_demo_owner', None)
            return redirect(url_for('sectest.admin_dashboard'))
        elif action == 'reset' and active('sectest'):
            with sqlite3.connect(database_path()) as conn:
                for table in ('notification_reads', 'notifications', 'demo_events', 'monthly_issues',
                              'plan_requests', 'payment_attempts', 'receipts', 'invoices', 'client_messages',
                              'client_requests', 'service_plans', 'registrations', 'messages'):
                    conn.execute('DELETE FROM ' + table)
                from sectest_plans import DEFAULTS
                conn.executemany('INSERT INTO service_plans VALUES (?,?,?,?,?)', DEFAULTS)
        else:
            abort(400)
        return redirect(url_for('sectest_demo.index'))
    return render_template('sectest/demo.html', admin=True, brand='sectest', brand_name='SecTest',
                           title='Modo de testes', enabled=active('sectest'))

@bp.app_template_global()
def sectest_demo_active():
    return active('sectest')
