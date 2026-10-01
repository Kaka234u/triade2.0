"""Conteúdo persistente do FK. As alterações não modificam os arquivos do site."""
import json
from urllib.parse import quote, urlsplit
from .data import business as defaults, services as default_services

PRICE_RANGES = [(85,250),(350,1200),(150,600),(250,700),(1000,3000),(120,350),(120,300)]

def init_content(conn):
    conn.executescript('''
      CREATE TABLE IF NOT EXISTS site_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS site_services (slug TEXT PRIMARY KEY, data TEXT NOT NULL, position INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1);
      CREATE TABLE IF NOT EXISTS page_edits (page TEXT NOT NULL, field TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(page,field));
      CREATE TABLE IF NOT EXISTS content_history (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT (datetime('now')), actor TEXT, action TEXT);
    ''')
    initial = dict(defaults, whatsapp_number='5585988388384', instagram_url='https://instagram.com/fk.autodetail',
                   instagram_label='@fk.autodetail', hero_image='static/images/hero-red-car.png',page_image='static/images/hero-s1000-carbon.webp')
    conn.execute('INSERT OR IGNORE INTO site_settings VALUES (?,?)',('business',json.dumps(initial,ensure_ascii=False)))
    if not conn.execute('SELECT 1 FROM site_settings WHERE key=?',('services_seeded',)).fetchone():
        for i,service in enumerate(default_services):
            entry=dict(service,price_min=PRICE_RANGES[i][0],price_max=PRICE_RANGES[i][1])
            conn.execute('INSERT OR IGNORE INTO site_services VALUES (?,?,?,1)',(entry['slug'],json.dumps(entry,ensure_ascii=False),i))
        conn.execute('INSERT INTO site_settings VALUES (?,?)',('services_seeded','true'))

def conn():
    from .routes import get_db
    return get_db()

def get_business():
    from flask import url_for
    row=conn().execute("SELECT value FROM site_settings WHERE key='business'").fetchone()
    result=json.loads(row['value'])
    for key in ('hero_image','page_image'):
        if result[key].startswith('static/'):
            result[key]=url_for('kaka.static',filename=result[key][7:])
    return result

def brl(value):
    return ('R$ '+f'{value:,.2f}').replace(',','X').replace('.',',').replace('X','.')

def get_services(include_hidden=False):
    rows=conn().execute('SELECT * FROM site_services '+('' if include_hidden else 'WHERE active=1 ')+'ORDER BY position,slug').fetchall()
    result=[]
    for row in rows:
        service=json.loads(row['data'])
        service.update(active=bool(row['active']),position=row['position'])
        service['price_label']=f"{brl(service['price_min'])} – {brl(service['price_max'])}"
        result.append(service)
    return result

def whatsapp_url(message='Olá, vim pelo site da FK Káka Detail e gostaria de solicitar informações sobre um serviço.'):
    return 'https://wa.me/'+get_business()['whatsapp_number']+'?text='+quote(message)

def safe_url(value, image=False):
    if not isinstance(value,str) or any(c in value for c in ['<','>','"',"'",'\\','\n','\r']):
        return False
    try:
        parts=urlsplit(value)
    except ValueError:
        return False
    if parts.scheme:
        return parts.scheme=='https' and bool(parts.netloc) or (not image and parts.scheme in {'tel','mailto'})
    return bool(value) and not value.startswith('//') and not any(ord(c)<32 for c in value)

def page_key(path):
    from flask import url_for
    prefix=url_for('kaka.home').rstrip('/')
    return path[len(prefix):] if prefix and path.startswith(prefix+'/') else path
