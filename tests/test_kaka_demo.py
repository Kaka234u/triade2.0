import sqlite3
from datetime import date, timedelta
import pytest
from test_integration import app, client, csrf, login, kaka, accounts
from test_operations import customer, invoice


@pytest.fixture(autouse=True)
def isolated_demo(tmp_path, monkeypatch):
    monkeypatch.setitem(app.config, 'FK_DEMO_DIR', str(tmp_path/'sandbox'))


def start(c):
    login(c)
    token=csrf(c,'/kaka/admin/testes')
    assert c.post('/kaka/admin/testes',data={'csrf_token':token,'action':'start'}).status_code==302
    return token


def demo_invoice(c, token):
    payload=dict(name='Cliente de teste',phone='85999999999',service='Lavagem detalhada',vehicle='Carro de teste',preferredDate=(date.today()+timedelta(days=2)).isoformat(),preferredPeriod='Tarde')
    r=c.post('/kaka/api/bookings',json=payload,headers={'X-CSRF-Token':token})
    assert r.status_code==200
    assert c.post('/kaka/pedidos/1/pagamentos',data=dict(csrf_token=token,reference='demo-invoice',total='120',due=date.today().isoformat(),description='Lavagem de teste')).status_code==302


def test_demo_requires_admin_and_csrf(client):
    assert client.get('/kaka/admin/testes').status_code==302
    customer(client)
    assert client.post('/kaka/admin/testes',data={'csrf_token':csrf(client),'action':'start'}).status_code==302
    login(client)
    assert client.post('/kaka/admin/testes',data={'action':'start'}).status_code==400
    assert not list(__import__('pathlib').Path(app.config['FK_DEMO_DIR']).glob('*.db'))


def test_isolated_flow_approval_decline_refund_no_provider(client,monkeypatch):
    invoice(client) # real data must survive all sandbox operations
    with app.app_context():
        before=[tuple(r) for r in kaka.get_db().execute('SELECT * FROM invoices')]
    token=start(client)
    import client_payments
    def no_network(*args,**kwargs):
        raise AssertionError('A demo must never read payment settings or call a provider')
    monkeypatch.setattr(client_payments,'settings',no_network)
    monkeypatch.setattr(client_payments.payments,'_mp',no_network)
    assert 'MODO DE TESTES' in client.get('/kaka/').text
    assert 'Nenhuma' in client.get('/kaka/admin/agendamentos').text
    demo_invoice(client,token)
    assert 'Aprovar pagamento' in client.get('/kaka/pagamento/1').text
    assert 'Aprovar pagamento' not in client.get('/sectest/login').text
    for action in ['simulate_declined','simulate_pending','simulate_paid','simulate_paid']:
        assert client.post('/kaka/pagamento/1',data={'csrf_token':token,'action':action}).status_code==302
    path=next(__import__('pathlib').Path(app.config['FK_DEMO_DIR']).glob('*.db'))
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT sum(amount) FROM receipts WHERE reversed=0').fetchone()[0]==12000
        assert db.execute('SELECT count(*) FROM payment_attempts').fetchone()[0]==0
    assert client.post('/kaka/pagamento/1',data={'csrf_token':token,'action':'simulate_refund'}).status_code==302
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM receipts WHERE reversed=0').fetchone()[0]==0
    assert client.post('/kaka/webhook/pagamentos',json={}).status_code==200
    assert client.post('/kaka/admin/testes',data={'csrf_token':token,'action':'reset'}).status_code==302
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM invoices').fetchone()[0]==0
    assert client.post('/kaka/admin/testes',data={'csrf_token':token,'action':'stop'}).status_code==302
    with app.app_context():
        assert [tuple(r) for r in kaka.get_db().execute('SELECT * FROM invoices')]==before
        assert kaka.get_db().execute('SELECT count(*) FROM receipts').fetchone()[0]==0
    assert 'MODO DE TESTES' not in client.get('/kaka/').text


def test_demo_does_not_leak_to_customer_or_other_admin(client):
    token=start(client);demo_invoice(client,token)
    other=app.test_client();customer(other,email='someone@example.test')
    assert other.get('/kaka/meus-pedidos/1').status_code==404
    assert 'MODO DE TESTES' not in other.get('/kaka/').text
    from werkzeug.security import generate_password_hash
    with app.app_context():
        accounts.db().execute("INSERT INTO accounts(brand,name,email,password_hash,role) VALUES ('kaka','Other','other-admin@example.test',?,'admin')",(generate_password_hash('OtherAdmin123!'),));accounts.db().commit()
    t=csrf(other)
    other.post('/kaka/admin/login',data=dict(csrf_token=t,email='other-admin@example.test',password='OtherAdmin123!'))
    other.post('/kaka/admin/testes',data=dict(csrf_token=t,action='start'))
    assert other.get('/kaka/meus-pedidos/1').status_code==404
    assert len(list(__import__('pathlib').Path(app.config['FK_DEMO_DIR']).glob('*.db')))==2


def test_no_demo_action_on_real_payment_and_no_shared_upload(client):
    token=invoice(client)
    result=client.post('/kaka/pagamento/1',data=dict(csrf_token=token,action='simulate_paid'))
    assert result.status_code in (200,400)
    with app.app_context():assert kaka.get_db().execute('SELECT count(*) FROM receipts').fetchone()[0]==0
    token=start(client)
    assert client.post('/kaka/admin/imagens',data=dict(csrf_token=token)).status_code==400
    assert client.post('/kaka/admin/testes',data=dict(action='reset')).status_code==400
    client.post('/kaka/admin/logout',data=dict(csrf_token=token))
    assert 'MODO DE TESTES' not in client.get('/kaka/').text
    # Logging out of the administrator preserves a pre-existing real customer session.
    assert client.get('/kaka/meus-pedidos').status_code==200


def test_kaka_public_pages_and_protected_booking(client):
    for path in ['/kaka/','/kaka/servicos','/kaka/servicos/lavagem-detalhada','/kaka/galeria','/kaka/contato','/kaka/sobre']:
        assert client.get(path).status_code==200
    for path in ['/kaka/agendamento','/kaka/orcamento','/kaka/meus-pedidos','/kaka/admin/testes']:
        assert client.get(path).status_code==302
    assert client.post('/kaka/api/bookings',json={}).status_code==401
    assert client.get('/sectest/').status_code==302
