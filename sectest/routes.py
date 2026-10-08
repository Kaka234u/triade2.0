"""API da nova versão SecTest adaptada ao portal Flask, sem servidor Node extra."""
import json
import os
import re
import sqlite3
from pathlib import Path
from flask import Blueprint, abort, g, jsonify, redirect, request, send_from_directory, url_for
from accounts import authenticate, csrf_token, logout_user, require_admin, verify_csrf

BASE_DIR = Path(__file__).resolve().parent
SITE_DIR = BASE_DIR / 'static_site'
DB_PATH = Path(os.environ.get('SECTEST_DB', BASE_DIR / 'database.db'))
app = Blueprint('sectest', __name__)

def get_db():
    if 'sectest_db' not in g:
        g.sectest_db = sqlite3.connect(DB_PATH)
        g.sectest_db.row_factory = sqlite3.Row
    return g.sectest_db

@app.teardown_app_request
def close_db(error=None):
    conn = g.pop('sectest_db', None)
    if conn is not None:
        conn.close()

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS registrations (id INTEGER PRIMARY KEY AUTOINCREMENT,
          empresa TEXT NOT NULL,cnpj TEXT,funcionarios TEXT NOT NULL,responsavel TEXT NOT NULL,
          email TEXT NOT NULL,telefone TEXT NOT NULL,servicos TEXT,mensagem TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT,
          nome TEXT NOT NULL,email TEXT NOT NULL,assunto TEXT NOT NULL,mensagem TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY);
        ''')
        # Preserva os registros recebidos no ZIP, sem importar senhas ou segredos do Node.
        seed = BASE_DIR / 'importacao_inicial.json'
        if seed.exists() and not conn.execute("SELECT 1 FROM migrations WHERE name='node_import'").fetchone():
            source = json.loads(seed.read_text(encoding='utf-8'))
            columns = {
                'registrations':['id','empresa','cnpj','funcionarios','responsavel','email','telefone','servicos','mensagem','created_at'],
                'messages':['id','nome','email','assunto','mensagem','created_at']}
            for table,keys in columns.items():
                for row in source.get(table,[]):
                    conn.execute(f"INSERT OR IGNORE INTO {table} ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",tuple(row[k] for k in keys))
            conn.execute("INSERT INTO migrations VALUES ('node_import')")

@app.get('/')
def index():
    return send_from_directory(SITE_DIR, 'index.html')

@app.get('/admin')
@require_admin('sectest')
def admin_dashboard():
    return send_from_directory(SITE_DIR, 'admin.html')

@app.get('/<path:filename>')
def page(filename):
    if filename=='cadastro.html':
        return redirect(url_for('sectest_plans.diagnostic'))
    if filename == 'admin.html':
        return redirect(url_for('sectest.admin_dashboard'))
    if filename not in {'index.html','sobre.html','servicos.html','cadastro.html','contato.html','style.css','script.js','favicon.svg'}:
        abort(404)
    return send_from_directory(SITE_DIR, filename)

@app.get('/api/csrf')
def csrf():
    response = jsonify(token=csrf_token())
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.before_request
def protect():
    if request.method == 'POST':
        verify_csrf()

def data():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, 'Envie um objeto JSON válido.')
    return body

def text(body, key, limit=200):
    return body.get(key, '').strip()[:limit] if isinstance(body.get(key, ''), str) else ''

def email_valid(value):
    return bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value))

@app.post('/api/cadastro')
def registration():
    from accounts import current_user
    if not current_user('sectest'):
        return jsonify(error='Entre na sua conta para solicitar e acompanhar o serviço.'), 401
    body = data()
    values = {key: text(body,key,2000 if key=='mensagem' else 200) for key in
              ['empresa','cnpj','funcionarios','responsavel','email','telefone','mensagem']}
    errors = {key: 'Preencha este campo.' for key in ['empresa','funcionarios','responsavel'] if not values[key]}
    if not email_valid(values['email']): errors['email'] = 'Informe um e-mail válido.'
    if not 10 <= len(re.sub(r'\D','',values['telefone'])) <= 13: errors['telefone'] = 'Informe telefone com DDD.'
    if body.get('consentimento') is not True: errors['consentimento'] = 'É necessário concordar para continuar.'
    if errors: return jsonify(error='Dados inválidos.',fields=errors), 400
    services = body.get('servicos', [])
    if not isinstance(services,list) or len(services)>30 or any(not isinstance(s,str) or len(s)>200 for s in services):
        return jsonify(error='Serviços inválidos.'), 400
    conn = get_db()
    cur = conn.execute('''INSERT INTO registrations (empresa,cnpj,funcionarios,responsavel,email,telefone,servicos,mensagem)
      VALUES (?,?,?,?,?,?,?,?)''', (*[values[k] for k in ['empresa','cnpj','funcionarios','responsavel','email','telefone']],json.dumps(services,ensure_ascii=False),values['mensagem']))
    from customer_portal import add_request
    add_request(conn,'sectest','CAD-'+str(cur.lastrowid),', '.join(services) or 'Diagnóstico',values['empresa']+'\n'+values['mensagem'])
    conn.commit()
    return jsonify(message='Cadastro recebido com sucesso.',id=cur.lastrowid), 201

@app.post('/api/contato')
def contact():
    body = data()
    values = {k:text(body,k,4000 if k=='mensagem' else 200) for k in ['nome','email','assunto','mensagem']}
    errors = {k:'Preencha este campo.' for k,v in values.items() if not v}
    if not email_valid(values['email']): errors['email'] = 'Informe um e-mail válido.'
    if errors: return jsonify(error='Dados inválidos.',fields=errors), 400
    cur = get_db().execute('INSERT INTO messages (nome,email,assunto,mensagem) VALUES (?,?,?,?)',tuple(values.values()))
    get_db().commit()
    return jsonify(message='Mensagem enviada com sucesso.',id=cur.lastrowid), 201

@app.post('/api/admin/login')
def admin_login():
    body = data()
    user,error,status = authenticate('sectest', body.get('username'),body.get('password'),True)
    return (jsonify(error=error),status) if error else jsonify(username=user['email'])

@app.post('/api/admin/logout')
def admin_logout():
    logout_user('sectest',True)
    return jsonify(ok=True)

@app.get('/api/admin/registrations')
@require_admin('sectest')
def registrations():
    rows=[]
    for row in get_db().execute('SELECT * FROM registrations ORDER BY id DESC'):
        item=dict(row)
        item['servicos']=json.loads(item['servicos'] or '[]')
        item['createdAt']=item.pop('created_at')
        rows.append(item)
    return jsonify(rows)

@app.get('/api/admin/messages')
@require_admin('sectest')
def messages():
    return jsonify([dict(row) for row in get_db().execute('SELECT * FROM messages ORDER BY id DESC')])

@app.get('/api/admin/stats')
@require_admin('sectest')
def stats():
    conn=get_db()
    return jsonify(total=conn.execute('SELECT count(*) FROM registrations').fetchone()[0],
        week=conn.execute("SELECT count(*) FROM registrations WHERE created_at>=datetime('now','-7 days')").fetchone()[0],
        messages=conn.execute('SELECT count(*) FROM messages').fetchone()[0],
        activeCompanies=conn.execute('SELECT count(DISTINCT empresa) FROM registrations').fetchone()[0])

@app.after_request
def private_headers(response):
    if '/admin' in request.path:
        response.headers['Cache-Control']='no-store'
        response.headers['X-Robots-Tag']='noindex, nofollow'
    return response
