"""Notificações por empresa, transacionais, com leitura individual por conta e papel."""
from flask import Blueprint, abort, jsonify, request, url_for
from accounts import current_user, verify_csrf


def init_notifications(conn):
    # Migração aditiva. Não reenvia eventos anteriores à instalação.
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS notifications (
      id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT UNIQUE NOT NULL,
      audience TEXT NOT NULL CHECK(audience IN ('customer','admin')),
      recipient_id INTEGER, request_id INTEGER, title TEXT NOT NULL, body TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now')));
    CREATE TABLE IF NOT EXISTS notification_reads (
      notification_id INTEGER NOT NULL, user_id INTEGER NOT NULL, administrator INTEGER NOT NULL,
      read_at TEXT NOT NULL DEFAULT (datetime('now')),
      PRIMARY KEY(notification_id,user_id,administrator));
    CREATE INDEX IF NOT EXISTS notification_recipient ON notifications(audience,recipient_id,id);
    CREATE TRIGGER IF NOT EXISTS notify_new_request AFTER INSERT ON client_requests BEGIN
      INSERT OR IGNORE INTO notifications(event_key,audience,request_id,title,body)
      VALUES('request:'||NEW.id,'admin',NEW.id,'Novo pedido',NEW.service);
    END;
    CREATE TRIGGER IF NOT EXISTS notify_message AFTER INSERT ON client_messages BEGIN
      INSERT OR IGNORE INTO notifications(event_key,audience,recipient_id,request_id,title,body)
      SELECT 'message:'||NEW.id,CASE WHEN NEW.administrator=1 THEN 'customer' ELSE 'admin' END,
        CASE WHEN NEW.administrator=1 THEN owner_id ELSE NULL END,NEW.request_id,
        'Nova mensagem','Há uma nova mensagem no pedido #'||NEW.request_id
      FROM client_requests WHERE id=NEW.request_id;
    END;
    CREATE TRIGGER IF NOT EXISTS notify_request_status AFTER UPDATE ON client_requests
      WHEN OLD.status IS NOT NEW.status OR OLD.confirmed_date IS NOT NEW.confirmed_date
        OR OLD.confirmed IS NOT NEW.confirmed BEGIN
      INSERT INTO notifications(event_key,audience,recipient_id,request_id,title,body)
      VALUES('status:'||NEW.id||':'||lower(hex(randomblob(16))),'customer',NEW.owner_id,NEW.id,
        'Atendimento atualizado','Pedido #'||NEW.id||': '||NEW.status||
        CASE WHEN NEW.confirmed_date<>'' THEN ' — '||NEW.confirmed_date ELSE '' END);
    END;
    CREATE TRIGGER IF NOT EXISTS notify_receipt AFTER INSERT ON receipts WHEN NEW.reversed=0 BEGIN
      INSERT OR IGNORE INTO notifications(event_key,audience,recipient_id,request_id,title,body)
      SELECT 'receipt:'||NEW.id,'customer',r.owner_id,r.id,'Pagamento confirmado',
        'Recebimento registrado. Confira o saldo nos pagamentos do pedido.'
      FROM invoices i JOIN client_requests r ON r.id=i.request_id WHERE i.id=NEW.invoice_id;
    END;
    CREATE TRIGGER IF NOT EXISTS notify_receipt_reapproved AFTER UPDATE ON receipts
      WHEN OLD.reversed=1 AND NEW.reversed=0 BEGIN
      INSERT OR IGNORE INTO notifications(event_key,audience,recipient_id,request_id,title,body)
      SELECT 'receipt:'||NEW.id,'customer',r.owner_id,r.id,'Pagamento confirmado',
        'Recebimento registrado. Confira o saldo nos pagamentos do pedido.'
      FROM invoices i JOIN client_requests r ON r.id=i.request_id WHERE i.id=NEW.invoice_id;
    END;
    ''')


def register_notifications(app, brand, prefix, get_db):
    bp = Blueprint(brand+'_notifications', __name__)

    def handle(admin, read=False):
        user = current_user(brand, admin)
        if not user:
            return jsonify(error='Sua sessão expirou.'), 401
        audience = 'admin' if admin else 'customer'
        conn = get_db()
        where = "n.audience=? AND (n.recipient_id IS NULL OR n.recipient_id=?)"
        params = (audience, user['id'])
        if read:
            verify_csrf()
            data = request.get_json(silent=True)
            if not isinstance(data, dict): abort(400)
            ident = data.get('id')
            if data.get('all') is True:
                # Só até o último ID que a interface realmente apresentou.
                through = data.get('through')
                if type(through) is not int or through < 0: abort(400)
                rows = conn.execute('SELECT n.id FROM notifications n WHERE '+where+' AND n.id<=?', params+(through,)).fetchall()
            else:
                if type(ident) is not int: abort(400)
                rows = conn.execute('SELECT n.id FROM notifications n WHERE '+where+' AND n.id=?', params+(ident,)).fetchall()
                if not rows: abort(404)
            conn.executemany('INSERT OR IGNORE INTO notification_reads(notification_id,user_id,administrator) VALUES (?,?,?)',
                [(r['id'],user['id'],int(admin)) for r in rows])
            conn.commit()
        joined = ''' FROM notifications n LEFT JOIN notification_reads r
          ON r.notification_id=n.id AND r.user_id=? AND r.administrator=? WHERE '''+where
        args = (user['id'],int(admin))+params
        unread = conn.execute('SELECT count(*)'+joined+' AND r.notification_id IS NULL', args).fetchone()[0]
        rows = conn.execute('SELECT n.*,r.read_at'+joined+' ORDER BY n.id DESC LIMIT 100', args).fetchall()
        items=[]
        for row in rows:
            item=dict(row)
            item['url']=url_for(brand+'_portal.'+('admin_detail' if admin else 'detail'),ident=row['request_id'])
            if row['title']=='Pagamento confirmado':
                item['url']=url_for(brand+'_finance.request_invoices',ident=row['request_id'])
            items.append(item)
        return jsonify(items=items,unread=unread,latest=rows[0]['id'] if rows else 0)

    @bp.get('/notificacoes')
    def customer(): return handle(False)
    @bp.post('/notificacoes/lidas')
    def customer_read(): return handle(False,True)
    @bp.get('/admin/notificacoes')
    def admin(): return handle(True)
    @bp.post('/admin/notificacoes/lidas')
    def admin_read(): return handle(True,True)
    @bp.after_request
    def private(response):
        response.headers['Cache-Control']='no-store'
        return response
    app.register_blueprint(bp,url_prefix=prefix)
