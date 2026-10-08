import sqlite3
from datetime import date, timedelta
from urllib.parse import quote
from bs4 import BeautifulSoup
from test_integration import app, client, csrf, login, kaka, sectest, accounts
from test_operations import customer, booking, invoice
from notifications import init_notifications


def test_entry_gate_customer_session_assets_and_vortex_unchanged(client):
    for brand in ['kaka','sectest']:
        response=client.get('/'+brand+'/')
        assert response.status_code==302 and '/'+brand+'/login?' in response.location
        assert client.get(response.location,follow_redirects=True).status_code==200
        for path in ['/login','/criar-conta','/admin/login']:
            assert client.get('/'+brand+path).status_code==200
    for path in ['/shared-static/brand-admin.css','/kaka/static/css/style.css','/sectest/style.css','/sectest/script.js']:
        assert client.get(path).status_code==200
    assert client.get('/vortex7/').status_code==200
    assert client.get('/').status_code==200
    assert client.post('/kaka/api/quotes',json={}).status_code==401
    customer(client)
    for path in ['/kaka/','/kaka/servicos','/kaka/agendamento','/kaka/galeria']:
        assert client.get(path).status_code==200
    assert client.get('/sectest/').status_code==302
    assert client.get('/kaka/admin').status_code==302


def test_safe_return_after_login(client):
    token=csrf(client)
    response=client.post('/kaka/login?next=/kaka/agendamento',data=dict(csrf_token=token,email='admin@example.test',password='TestPassword123!'))
    assert response.location=='/kaka/agendamento'
    for target in ['https://evil.test','//evil.test','/%2Fevil.test','/sectest/','/kaka/admin','/kaka/login','/kaka/logout','/kaka/api/bookings','/kaka/\\evil']:
        with app.test_request_context():
            from accounts import safe_next
            assert safe_next('kaka',target) is None,target


def test_all_admin_pages_share_navigation(client):
    for brand,paths in [('kaka',['','/servicos','/paginas','/imagens','/configuracoes','/solicitacoes','/agendamentos','/faturamento']),('sectest',['','/agendamentos','/faturamento','/planos','/contratos'])]:
        login(client,brand)
        reference=None
        for path in paths:
            r=client.get('/'+brand+'/admin'+path);assert r.status_code==200
            soup=BeautifulSoup(r.data,'html.parser');nav=soup.select_one('nav.grouped-nav');assert nav
            links=[(a['href'],a.text.strip()) for a in nav.select('a')]
            if reference is None:reference=links
            assert links==reference
            active=nav.select('a[aria-current=page]');assert active,path
            assert all(a.find_parent('details').has_attr('open') for a in active)
            assert not any('/'+('sectest' if brand=='kaka' else 'kaka')+'/' in href or '/vortex7/' in href for href,_ in links)
            assert soup.select_one('[data-notifications-url]')['data-notifications-url']=='/'+brand+'/admin/notificacoes'


def test_new_request_redirect_success_and_error(client):
    token=customer(client)
    payload=dict(name='Cliente',phone='85988887777',service='Lavagem',vehicle='Carro',preferredDate=(date.today()+timedelta(days=2)).isoformat(),preferredPeriod='Tarde')
    bad=client.post('/kaka/api/bookings',json={**payload,'phone':'1'},headers={'X-CSRF-Token':token})
    assert bad.status_code==400 and 'redirect_url' not in bad.json
    good=client.post('/kaka/api/bookings',json=payload,headers={'X-CSRF-Token':token})
    assert good.status_code==200 and good.json['redirect_url']=='/kaka/meus-pedidos/1?enviado=1'
    detail=client.get(good.json['redirect_url']);assert detail.status_code==200
    assert 'Solicitação enviada com sucesso' in detail.text and 'Pagamentos disponíveis' in detail.text
    quote_data=dict(name='Cliente',phone='85988887777',vehicleType='Carro',brand='Marca',model='Modelo',service='Polimento',condition='Uso diário',consent=True)
    good=client.post('/kaka/api/quotes',json=quote_data,headers={'X-CSRF-Token':token})
    assert '/kaka/meus-pedidos/2?' in good.json['redirect_url']
    assert client.post('/kaka/api/quotes',json=quote_data,headers={'X-CSRF-Token':token}).status_code==429


def test_notifications_target_role_brand_and_read_state(client):
    token=booking(client)
    assert client.get('/kaka/notificacoes').json['unread']==0
    assert client.get('/kaka/admin/notificacoes').status_code==401
    staff=app.test_client();login(staff)
    notifications=staff.get('/kaka/admin/notificacoes').json
    assert notifications['unread']==1
    ident=notifications['items'][0]['id']
    assert client.post('/kaka/notificacoes/lidas',json={'id':ident},headers={'X-CSRF-Token':token}).status_code==404
    assert staff.post('/kaka/admin/notificacoes/lidas',json={'id':ident}).status_code==400
    headers={'X-CSRF-Token':csrf(staff,'/kaka/admin/login')}
    assert staff.post('/kaka/admin/notificacoes/lidas',json={'id':ident},headers=headers).json['unread']==0
    assert staff.post('/kaka/admin/notificacoes/lidas',json={'id':ident},headers=headers).json['unread']==0
    other_staff=app.test_client();login(other_staff,'sectest')
    assert other_staff.get('/sectest/admin/notificacoes').json['unread']==0
    assert other_staff.get('/kaka/admin/notificacoes').status_code==401
    assert client.get('/sectest/notificacoes').status_code==401
    assert staff.get('/vortex7/admin/').status_code==302
    # Another FK administrator has an independent unread marker.
    from werkzeug.security import generate_password_hash
    with app.app_context():
        accounts.db().execute("INSERT INTO accounts(brand,name,email,password_hash,role) VALUES ('kaka','Staff','staff@example.test',?,'admin')",(generate_password_hash('AnotherStaff123!'),));accounts.db().commit()
    another=app.test_client();t=csrf(another)
    another.post('/kaka/admin/login',data=dict(csrf_token=t,email='staff@example.test',password='AnotherStaff123!'))
    assert another.get('/kaka/admin/notificacoes').json['unread']==1


def test_chat_async_incremental_no_duplicate_and_client_isolation(client):
    token=booking(client);staff=app.test_client();login(staff);st=csrf(staff,'/kaka/admin/login')
    h={'Accept':'application/json'}
    msg=dict(csrf_token=token,action='message',message='<script>private</script>')
    assert client.post('/kaka/meus-pedidos/1',data=msg,headers=h).json=={'ok':True}
    assert client.post('/kaka/meus-pedidos/1',data=msg,headers=h).json=={'ok':True}
    assert staff.get('/kaka/admin/notificacoes').json['unread']==2
    assert staff.get('/kaka/conversas/1/mensagens?role=admin').json['messages'][0]['body']=='<script>private</script>'
    assert staff.get('/kaka/conversas/1/mensagens?role=admin&after=1').json['messages']==[]
    assert staff.get('/kaka/conversas/1/mensagens').status_code==401
    assert client.get('/kaka/conversas/1/mensagens?role=admin').status_code==401
    assert staff.post('/kaka/admin/agendamentos/1',data=dict(csrf_token=st,action='message',message='Resposta'),headers=h).json['ok']
    assert client.get('/kaka/notificacoes').json['unread']==1
    other=app.test_client();customer(other,email='other@example.test')
    assert other.get('/kaka/conversas/1/mensagens').status_code==404
    assert other.get('/kaka/notificacoes').json['unread']==0
    note=client.get('/kaka/notificacoes').json['items'][0]['id']
    assert other.post('/kaka/notificacoes/lidas',json={'id':note},headers={'X-CSRF-Token':csrf(other)}).status_code==404
    assert client.get('/kaka/conversas/1/mensagens?after=bad').status_code==400


def test_status_and_payment_notifications_atomic_idempotent(client):
    token=invoice(client)
    update=dict(csrf_token=token,action='confirm',status='agendado',total='120',confirmed_date='2026-12-20T14:00')
    for _ in range(2):assert client.post('/kaka/admin/agendamentos/1',data=update).status_code==302
    assert client.get('/kaka/notificacoes').json['unread']==1
    receive=dict(csrf_token=token,action='receive',amount='20',paid_on=date.today().isoformat(),method='pix',reference='receipt-only-once')
    for _ in range(2):assert client.post('/kaka/admin/faturamento/1',data=receive).status_code==302
    assert client.get('/kaka/notificacoes').json['unread']==2
    with app.app_context():
        conn=kaka.get_db();before=conn.execute('SELECT count(*) FROM notifications').fetchone()[0]
        conn.execute("INSERT INTO client_messages(request_id,sender_id,administrator,body) VALUES (1,1,0,'rollback')");conn.rollback()
        assert conn.execute('SELECT count(*) FROM notifications').fetchone()[0]==before
        from client_payments import apply_payment
        conn.execute("INSERT INTO payment_attempts(reference,invoice_id,amount) VALUES ('FKtest',1,10000)");conn.commit()
        payment=dict(id=789,external_reference='FKtest',transaction_amount=100,currency_id='BRL',status='approved')
        apply_payment(conn,payment);apply_payment(conn,payment)
    notes=client.get('/kaka/notificacoes').json
    assert notes['unread']==3
    response=client.post('/kaka/notificacoes/lidas',json={'all':True,'through':notes['latest']},headers={'X-CSRF-Token':token})
    assert response.json['unread']==0


def test_migration_preserves_records_and_read_markers(client):
    invoice(client)
    with app.app_context():
        conn=kaka.get_db()
        tables=['client_requests','quote_requests','booking_requests','invoices','receipts','site_settings','site_services','notifications','notification_reads']
        before={t:[tuple(r) for r in conn.execute('SELECT * FROM '+t)] for t in tables}
        init_notifications(conn);init_notifications(conn)
        after={t:[tuple(r) for r in conn.execute('SELECT * FROM '+t)] for t in tables}
        assert before==after


def test_fk_uses_vortex_receiver_without_admin_access(client,tmp_path,monkeypatch):
    import vortex7.common as common
    from client_payments import settings
    path=tmp_path/'receiver.db'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT)')
        conn.execute("INSERT INTO settings VALUES ('pix_key','receiver@example.test')")
    monkeypatch.setattr(common,'DB_PATH',str(path))
    assert settings()['pix_key']=='receiver@example.test'
    login(client)
    assert client.get('/vortex7/admin/configuracoes').status_code==302
    assert client.get('/sectest/admin/faturamento').status_code==302


def test_sectest_request_messages_and_notifications(client):
    token=customer(client,'sectest')
    data=dict(csrf_token=token,plan='pequeno',visits='100',people='2',sites='1',revenue='0',attacked='nao',sensitive='nao',action='submit')
    result=client.post('/sectest/diagnostico',data=data)
    assert result.location=='/sectest/meus-pedidos/1?enviado=1'
    staff=app.test_client();login(staff,'sectest');st=csrf(staff,'/sectest/admin/login')
    assert staff.get('/sectest/admin/notificacoes').json['unread']==1
    assert client.post('/sectest/meus-pedidos/1',data=dict(csrf_token=token,action='message',message='Mensagem SecTest'),headers={'Accept':'application/json'}).json['ok']
    assert staff.get('/sectest/conversas/1/mensagens?role=admin').json['messages'][0]['body']=='Mensagem SecTest'
    assert staff.post('/sectest/admin/agendamentos/1',data=dict(csrf_token=st,action='message',message='Resposta SecTest'),headers={'Accept':'application/json'}).json['ok']
    assert client.get('/sectest/notificacoes').json['unread']==1
    login(staff,'kaka')
    assert staff.get('/kaka/admin/notificacoes').json['unread']==0
    assert staff.get('/kaka/conversas/1/mensagens?role=admin').status_code==404


def test_notification_reads_survive_new_session(client):
    booking(client);staff=app.test_client();login(staff)
    info=staff.get('/kaka/admin/notificacoes').json
    token=csrf(staff,'/kaka/admin/login')
    staff.post('/kaka/admin/notificacoes/lidas',json={'all':True,'through':info['latest']},headers={'X-CSRF-Token':token})
    staff.post('/kaka/admin/logout',data={'csrf_token':token})
    login(staff)
    assert staff.get('/kaka/admin/notificacoes').json['unread']==0


def test_same_browser_two_roles_do_not_widen_customer_conversation(client):
    booking(client)
    other=app.test_client();customer(other,email='second@example.test')
    login(other)
    # Explicit customer route remains private even if an administrator session coexists.
    assert other.get('/kaka/conversas/1/mensagens?role=customer').status_code==404
    assert other.get('/kaka/conversas/1/mensagens?role=admin').status_code==200
    assert other.get('/kaka/meus-pedidos/1').status_code==404


def test_real_pix_render_uses_saved_settings_without_admin_panel(client,tmp_path,monkeypatch):
    invoice(client)
    import vortex7.common as common
    path=tmp_path/'vortex-config.db'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT)')
        conn.executemany('INSERT INTO settings VALUES (?,?)',[('pix_key','receiver@example.test'),('pix_receiver_name','Recebedor de teste'),('pix_city','FORTALEZA'),('test_mode','0')])
    monkeypatch.setattr(common,'DB_PATH',str(path))
    result=client.get('/kaka/pagamento/1')
    assert result.status_code==200
    assert 'receiver@example.test' in result.text and 'DEMONSTRACAO' not in result.text
    assert client.get('/vortex7/admin/configuracoes').status_code==302
