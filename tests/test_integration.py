import io
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import pytest
from bs4 import BeautifulSoup
from PIL import Image
from werkzeug.security import generate_password_hash

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
BOOT=Path(tempfile.mkdtemp(prefix='triade-tests-'))
for env,file in [('TRIADE_AUTH_DB','auth.db'),('KAKA_DB','kaka.db'),('SECTEST_DB','sectest.db'),('VORTEX7_DB','vortex.db')]:
    os.environ[env]=str(BOOT/file)
os.environ['SECRET_KEY']='only-for-automated-tests'
os.environ['ADMIN_PASSWORD']='OnlyForVortexTests123!'
from app import app
import accounts
import kaka.routes as kaka
import sectest.routes as sectest

@pytest.fixture
def client(tmp_path,monkeypatch):
    app.config.update(TESTING=True)
    monkeypatch.setattr(accounts,'AUTH_DB',tmp_path/'accounts.db')
    monkeypatch.setattr(kaka,'DB_PATH',tmp_path/'kaka.db')
    monkeypatch.setattr(sectest,'DB_PATH',tmp_path/'sectest.db')
    # init_accounts registers hooks and CLI once; copy its empty schema instead.
    with sqlite3.connect(BOOT/'auth.db') as source, sqlite3.connect(accounts.AUTH_DB) as target: source.backup(target)
    with app.app_context():
        kaka.init_db();sectest.init_db()
        from customer_portal import init_portal
        from finance import init_finance
        from client_payments import init_payments
        from sectest_plans import init_plans
        for conn in (kaka.get_db(),sectest.get_db()):
            init_portal(conn);init_finance(conn);init_payments(conn);conn.commit()
        init_plans(sectest.get_db());sectest.get_db().commit()
        sectest.get_db().execute('DELETE FROM registrations')
        sectest.get_db().execute('DELETE FROM messages')
        sectest.get_db().commit()
        for brand in ['kaka','sectest']:
            accounts.db().execute('INSERT INTO accounts (brand,name,email,password_hash,role) VALUES (?,?,?,?,?)',
                (brand,'Admin','admin@example.test',generate_password_hash('TestPassword123!'),'admin'))
        accounts.db().commit()
    return app.test_client()

def csrf(client,path='/kaka/login'):
    soup=BeautifulSoup(client.get(path).data,'html.parser')
    return soup.select_one('input[name=csrf_token]')['value']

def login(client,brand='kaka',admin=True):
    path=f'/{brand}/admin/login' if admin else f'/{brand}/login'
    return client.post(path,data={'email':'admin@example.test','password':'TestPassword123!','csrf_token':csrf(client,path)})

def test_public_pages_assets_prices_and_hidden_admin(client):
    paths=['/','/vortex7/','/vortex7/login','/kaka/','/kaka/servicos','/kaka/galeria','/kaka/sobre','/kaka/contato','/kaka/faq','/kaka/orcamento','/kaka/agendamento',
      '/kaka/politicas/privacidade','/kaka/politicas/agendamento','/kaka/politicas/cancelamento','/sectest/','/sectest/sobre.html','/sectest/servicos.html','/sectest/cadastro.html','/sectest/contato.html','/sectest/login']
    for path in paths:
        response=client.get(path,follow_redirects=True)
        assert response.status_code==200,path
        soup=BeautifulSoup(response.data,'html.parser')
        for node in soup.select('img[src],script[src],link[rel=stylesheet],link[rel=icon]'):
            value=node.get('src') or node.get('href')
            target=urlsplit(urljoin('http://localhost'+path,value))
            if target.hostname=='localhost': assert client.get(target.path).status_code==200,(path,target.path)
        if path.startswith('/kaka'):
            assert not soup.select('a[href*="/admin"]')
    soup=BeautifulSoup(client.get('/kaka/servicos').data,'html.parser')
    prices=soup.select('.service-price')
    assert len(prices)==7
    assert all('R$' in p.text and '–' in p.text for p in prices)
    for a in soup.select('a[href^="/kaka/servicos/"]'):
        assert b'service-price' in client.get(a['href']).data

def test_registration_login_logout_and_brand_isolation(client):
    for brand in ['kaka','sectest']:
        path=f'/{brand}/criar-conta'
        token=csrf(client,path)
        data={'name':'Cliente','email':'client@example.test','password':'CustomerPass123','confirm_password':'CustomerPass123','csrf_token':token,'role':'admin'}
        assert client.post(path,data=data).status_code==302
        assert client.post(f'/{brand}/login',data={'email':data['email'],'password':data['password'],'csrf_token':token}).status_code==302
        assert client.get(f'/{brand}/conta',follow_redirects=True).status_code==200
        assert client.get(f'/{brand}/admin').status_code==302
        assert client.post(f'/{brand}/admin/login',data={'email':data['email'],'password':data['password'],'csrf_token':token}).status_code==401
        assert client.post(f'/{brand}/logout',data={'csrf_token':token}).status_code==302
        assert client.get(f'/{brand}/conta').status_code==302
    login(client,'kaka')
    assert client.get('/kaka/admin').status_code==200
    assert client.get('/sectest/admin').status_code==302
    assert client.get('/sectest/api/admin/registrations').status_code==401

def test_security_csrf_rate_limit_and_no_open_redirect(client):
    assert client.post('/kaka/admin/login',data={'email':'admin@example.test','password':'TestPassword123!'}).status_code==400
    token=csrf(client)
    for _ in range(10):
        assert client.post('/kaka/login',data={'email':'bad@example.test','password':'incorrect','csrf_token':token}).status_code==401
    assert client.post('/kaka/login',data={'email':'bad@example.test','password':'incorrect','csrf_token':token}).status_code==429
    response=login(client)
    assert response.location=='/kaka/admin'
    assert client.post('/kaka/admin/configuracoes',data={}).status_code==400
    assert client.post('/kaka/admin/api/conteudo',json={'page':'/kaka/','changes':{} }).status_code==400
    assert client.get('/kaka/admin').headers['Cache-Control']=='no-store'

def test_admin_pages_prices_persistence_and_validation(client):
    login(client)
    for path in ['','/servicos','/configuracoes','/paginas','/imagens','/solicitacoes']:
        assert client.get('/kaka/admin'+path).status_code==200,path
    token=csrf(client,'/kaka/admin/servicos')
    data={'csrf_token':token,'slug':'lavagem-detalhada','name':'Lavagem revisada','summary':'Resumo','description':'Descrição','price_min':'120','price_max':'500','position':'0','active':'on','steps':'Passo 1\nPasso 2','faq':'Pergunta? | Resposta.'}
    assert client.post('/kaka/admin/servicos',data=data).status_code==302
    html=client.get('/kaka/servicos/lavagem-detalhada').get_data(as_text=True)
    assert 'R$ 120,00 – R$ 500,00' in html and 'Lavagem revisada' in html
    data['price_max']='100'
    assert client.post('/kaka/admin/servicos',data=data).status_code==400
    assert 'R$ 120,00 – R$ 500,00' in client.get('/kaka/servicos').get_data(as_text=True)
    data.update(price_max='500',active='')
    assert client.post('/kaka/admin/servicos',data=data).status_code==302
    assert client.get('/kaka/servicos/lavagem-detalhada').status_code==404

def test_editor_escaped_content_shared_fields_and_restore(client):
    assert b'fk-editor-data' not in client.get('/kaka/?editar=1').data
    login(client)
    soup=BeautifulSoup(client.get('/kaka/?editar=1').data,'html.parser')
    payload=json.loads(soup.select_one('#fk-editor-data').string)
    field=soup.select_one('h1 [data-fk-edit]')['data-fk-edit']
    shared=soup.select_one('footer [data-fk-edit]')['data-fk-edit']
    headers={'X-CSRF-Token':payload['csrf']}
    assert client.post('/kaka/admin/api/conteudo',headers=headers,json={'page':'/kaka/','changes':{field:'<script>alert(1)</script>',shared:'Rodapé alterado'}}).status_code==200
    public=client.get('/kaka/').get_data(as_text=True)
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in public
    assert '<script>alert(1)</script>' not in public
    assert 'Rodapé alterado' in client.get('/kaka/contato').get_data(as_text=True)
    urlfield=next(k for k in payload['fields'] if k.startswith('src:'))
    assert client.post('/kaka/admin/api/conteudo',headers=headers,json={'page':'/kaka/','changes':{urlfield:'javascript:alert(1)'}}).status_code==400
    assert client.post('/kaka/admin/api/conteudo',headers=headers,json={'page':'/kaka/','reset':True}).status_code==200
    assert '&lt;script&gt;' not in client.get('/kaka/').get_data(as_text=True)

def test_sectest_forms_admin_data_and_logout(client):
    login(client,'sectest',admin=False)
    token=client.get('/sectest/api/csrf').json['token']; headers={'X-CSRF-Token':token}
    valid={'empresa':'Empresa <teste>','funcionarios':'1-10','responsavel':'Responsável','email':'contact@example.test','telefone':'85988888888','servicos':['Monitoramento'],'consentimento':True,'mensagem':'Preciso de diagnóstico.'}
    assert client.post('/sectest/api/cadastro',json=valid).status_code==400
    assert client.post('/sectest/api/cadastro',json={**valid,'consentimento':False},headers=headers).status_code==400
    assert client.post('/sectest/api/cadastro',json=valid,headers=headers).status_code==201
    assert client.post('/sectest/api/contato',json={'nome':'Nome','email':'contact@example.test','assunto':'Orçamento','mensagem':'Mensagem de teste'},headers=headers).status_code==201
    assert client.get('/sectest/api/admin/stats').status_code==401
    assert login(client,'sectest').status_code==302
    assert client.get('/sectest/admin').status_code==200
    assert client.get('/sectest/api/admin/stats').json=={'total':1,'week':1,'messages':1,'activeCompanies':1}
    assert client.get('/sectest/api/admin/registrations').json[0]['empresa']==valid['empresa']
    assert client.get('/sectest/api/admin/messages').json[0]['mensagem']=='Mensagem de teste'
    assert client.post('/sectest/api/admin/logout',headers=headers).status_code==200
    assert client.get('/sectest/api/admin/registrations').status_code==401

def test_cli_admin_and_settings(client):
    result=app.test_cli_runner().invoke(args=['criar-admin','--marca','kaka','--email','owner@example.test','--password','LongPassword123!'])
    assert result.exit_code==0,result.output
    login(client)
    soup=BeautifulSoup(client.get('/kaka/admin/configuracoes').data,'html.parser')
    data={i['name']:i.get('value','') for i in soup.select('main input[name]')}
    data['phone']='(85) 99999-1111';data['whatsapp_number']='5585999991111'
    assert client.post('/kaka/admin/configuracoes',data=data).status_code==302
    html=client.get('/kaka/contato').get_data(as_text=True)
    assert 'https://wa.me/5585999991111' in html
    assert 'tel:+5585999991111' in html
    assert '(85) 99999-1111' in html

def test_fk_requests_and_status_management(client):
    from datetime import date, timedelta
    quote={'name':'Cliente','phone':'85988887777','vehicleType':'Carro','brand':'Marca','model':'Modelo','service':'Lavagem detalhada','condition':'Uso diário','consent':True}
    response=client.post('/kaka/api/quotes',json=quote)
    assert response.status_code==200
    ident=response.json['id']
    assert client.post('/kaka/api/quotes',json=quote).status_code==429
    booking={'name':'Cliente','phone':'85988887777','service':'Lavagem detalhada','vehicle':'Carro','preferredDate':(date.today()+timedelta(days=2)).isoformat(),'preferredPeriod':'Tarde'}
    login(client,admin=False)
    assert client.post('/kaka/api/bookings',json=booking,headers={'X-CSRF-Token':csrf(client)}).status_code==200
    login(client)
    token=csrf(client,'/kaka/admin/solicitacoes')
    assert client.post('/kaka/admin/solicitacoes',data={'csrf_token':token,'kind':'quote','id':ident,'status':'confirmed'}).status_code==302
    with app.app_context():
        assert kaka.get_db().execute('SELECT status FROM quote_requests WHERE id=?',(ident,)).fetchone()[0]=='confirmed'

def test_image_upload_validation(client,tmp_path,monkeypatch):
    import kaka.admin as admin
    (tmp_path/'static').mkdir()
    monkeypatch.setattr(admin,'BASE_DIR',tmp_path)
    login(client)
    token=csrf(client,'/kaka/admin/imagens')
    picture=Image.new('RGB',(20,20),'red');stream=io.BytesIO();picture.save(stream,'PNG');stream.seek(0)
    assert client.post('/kaka/admin/imagens',data={'csrf_token':token,'image':(stream,'image.png')},content_type='multipart/form-data').status_code==302
    uploaded=list((tmp_path/'static/uploads').glob('*.webp'))
    assert len(uploaded)==1
    assert Image.open(uploaded[0]).format=='WEBP'
    assert client.post('/kaka/admin/imagens',data={'csrf_token':token,'image':(io.BytesIO(b'<script>bad</script>'),'image.png')},content_type='multipart/form-data').status_code==400

def test_sectest_import_once(client):
    with app.app_context():
        conn=sectest.get_db()
        conn.execute("DELETE FROM migrations WHERE name='node_import'");conn.commit()
        sectest.init_db()
        seed=json.loads((sectest.BASE_DIR/'importacao_inicial.json').read_text(encoding='utf-8'))
        assert conn.execute('SELECT count(*) FROM registrations').fetchone()[0]==len(seed['registrations'])
        sectest.init_db()
        assert conn.execute('SELECT count(*) FROM registrations').fetchone()[0]==len(seed['registrations'])
