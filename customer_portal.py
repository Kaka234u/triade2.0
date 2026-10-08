"""Atendimentos privados por empresa. Identidade vem sempre da sessão."""
from functools import wraps
from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from accounts import current_user, require_admin, verify_csrf


def init_portal(conn):
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS client_requests (
      id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, source_id TEXT UNIQUE,
      service TEXT NOT NULL, details TEXT NOT NULL DEFAULT '',
      requested_date TEXT NOT NULL DEFAULT '', confirmed_date TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'aguardando pagamento',
      total_cents INTEGER NOT NULL DEFAULT 0, confirmed INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT (datetime('now')));
    CREATE TABLE IF NOT EXISTS client_messages (
      id INTEGER PRIMARY KEY, request_id INTEGER NOT NULL, sender_id INTEGER NOT NULL,
      administrator INTEGER NOT NULL, body TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now')));
    CREATE INDEX IF NOT EXISTS client_request_owner ON client_requests(owner_id,id);
    CREATE INDEX IF NOT EXISTS client_message_request ON client_messages(request_id,id);
    ''')


def add_request(conn, brand, source_id, service, details='', requested_date=''):
    user = current_user(brand)
    if not user:
        return None
    cursor = conn.execute('''INSERT INTO client_requests
      (owner_id,source_id,service,details,requested_date) VALUES (?,?,?,?,?)''',
      (user['id'], source_id, service, details, requested_date))
    return cursor.lastrowid


def register_portal(app, brand, prefix, get_db):
    bp = Blueprint(brand + '_portal', __name__)

    def customer_required(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not current_user(brand):
                return redirect(url_for(brand + '_accounts.login'))
            if request.method == 'POST':
                verify_csrf()
            return view(*args, **kwargs)
        return wrapper

    def render(name, **context):
        from finance import money
        return render_template('portal_clients/' + name, brand=brand,
          brand_name='FK Káka Autodetail' if brand == 'kaka' else 'SecTest', money=money, **context)

    @bp.after_request
    def private(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    @bp.get('/meus-pedidos')
    @customer_required
    def index():
        rows = get_db().execute('SELECT * FROM client_requests WHERE owner_id=? ORDER BY id DESC',
                                (current_user(brand)['id'],)).fetchall()
        return render('list.html', rows=rows, admin=False, title='Meus serviços')

    @bp.get('/admin/agendamentos')
    @require_admin(brand)
    def admin_list():
        rows = get_db().execute('SELECT * FROM client_requests ORDER BY id DESC').fetchall()
        return render('list.html', rows=rows, admin=True, title='Agendamentos e conversas')

    def request_page(ident, admin):
        conn = get_db()
        user = current_user(brand, admin)
        row = conn.execute('SELECT * FROM client_requests WHERE id=?', (ident,)).fetchone()
        if not row or (not admin and row['owner_id'] != user['id']):
            abort(404)
        error = None
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'message':
                body = request.form.get('message', '').strip()
                if not 1 <= len(body) <= 4000:
                    error = 'Escreva uma mensagem de até 4.000 caracteres.'
                else:
                    # Evita mensagens idênticas consecutivas causadas por envio repetido.
                    last = conn.execute('SELECT * FROM client_messages WHERE request_id=? ORDER BY id DESC LIMIT 1', (ident,)).fetchone()
                    if not last or last['body'] != body or last['sender_id'] != user['id'] or last['administrator'] != int(admin):
                        conn.execute('INSERT INTO client_messages(request_id,sender_id,administrator,body) VALUES (?,?,?,?)',
                                     (ident,user['id'],int(admin),body))
            elif admin and action == 'confirm':
                from datetime import datetime
                from decimal import Decimal, InvalidOperation
                status = request.form.get('status')
                when = request.form.get('confirmed_date','').strip()
                try:
                    total = Decimal(request.form.get('total','').replace(',','.'))
                    if not total.is_finite() or total < 0 or total > 1000000:
                        raise ValueError()
                    if status not in ('aguardando pagamento','agendado','finalizado'):
                        raise ValueError()
                    if when:
                        datetime.fromisoformat(when)
                    if status in ('agendado','finalizado') and not when:
                        raise ValueError()
                    conn.execute('UPDATE client_requests SET status=?,total_cents=?,confirmed_date=?,confirmed=? WHERE id=?',
                      (status,int(total*100),when,int(status in ('agendado','finalizado')),ident))
                    if brand=='kaka':
                        legacy_status={'aguardando pagamento':'pending_manual_confirmation','agendado':'confirmed','finalizado':'completed'}[status]
                        conn.execute('UPDATE booking_requests SET status=? WHERE id=?',(legacy_status,row['source_id']))
                        conn.execute('UPDATE quote_requests SET status=? WHERE id=?',(legacy_status,row['source_id']))
                except (InvalidOperation,ValueError):
                    error = 'Revise o valor, o status e a data. Para confirmar ou finalizar, informe a data combinada.'
            else:
                abort(400)
            if error:
                conn.rollback()
            else:
                conn.commit()
                return redirect(url_for(brand+'_portal.'+('admin_detail' if admin else 'detail'),ident=ident))
        messages = conn.execute('SELECT * FROM client_messages WHERE request_id=? ORDER BY id', (ident,)).fetchall()
        from accounts import db as account_db
        owner=account_db().execute('SELECT name,email FROM accounts WHERE id=? AND brand=?',(row['owner_id'],brand)).fetchone()
        return render('detail.html', row=row, messages=messages, owner=owner, admin=admin, title=row['service'], error=error), 400 if error else 200

    @bp.route('/meus-pedidos/<int:ident>',methods=['GET','POST'])
    @customer_required
    def detail(ident):
        return request_page(ident,False)

    @bp.route('/admin/agendamentos/<int:ident>',methods=['GET','POST'])
    @require_admin(brand)
    def admin_detail(ident):
        return request_page(ident,True)

    @bp.get('/conversas/<int:ident>/mensagens')
    def messages(ident):
        user=current_user(brand)
        admin=current_user(brand,True)
        if not user and not admin:abort(401)
        row=get_db().execute('SELECT owner_id FROM client_requests WHERE id=?',(ident,)).fetchone()
        if not row or (not admin and row['owner_id']!=user['id']):abort(404)
        messages=get_db().execute('SELECT id,administrator,body,created_at FROM client_messages WHERE request_id=? ORDER BY id',(ident,)).fetchall()
        return jsonify(messages=[dict(m) for m in messages])

    app.register_blueprint(bp,url_prefix=prefix)
