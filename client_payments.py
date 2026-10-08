"""Reusa o recebedor Vortex7 sem compartilhar acesso administrativo."""
import os
import secrets
import sqlite3
import hashlib
import hmac
from datetime import date
from flask import Blueprint, abort, redirect, render_template, request, url_for
from accounts import current_user, verify_csrf
from finance import cents, invoice_rows, money
from vortex7 import payments


def settings():
    from vortex7.common import DB_PATH, load_settings
    # Conexão própria: nunca mistura o banco Vortex com o banco da empresa.
    if not DB_PATH.exists():return {}
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory=sqlite3.Row
        return load_settings(conn)


def init_payments(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS payment_attempts (
      reference TEXT PRIMARY KEY,invoice_id INTEGER NOT NULL,amount INTEGER NOT NULL,
      preference TEXT,checkout_url TEXT,created_at TEXT DEFAULT (datetime('now')))''')


def apply_payment(conn,payment):
    attempt=conn.execute('SELECT * FROM payment_attempts WHERE reference=?',(payment.get('external_reference',''),)).fetchone()
    if not attempt or payment.get('currency_id')!='BRL' or cents(payment.get('transaction_amount',0))!=attempt['amount']:
        return False
    reference='mp:'+str(payment['id'])
    status=payment.get('status')
    if status=='approved':
        refund=cents(payment.get('transaction_amount_refunded',0))
        amount=max(0,attempt['amount']-refund)
        if amount:
            conn.execute('''INSERT INTO receipts(invoice_id,amount,method,paid_on,actor,reference)
              VALUES (?,?,'mercadopago',?,'Mercado Pago',?) ON CONFLICT(reference)
              DO UPDATE SET amount=excluded.amount,reversed=0''',
              (attempt['invoice_id'],amount,str(payment.get('date_approved') or date.today().isoformat())[:10],reference))
        else:conn.execute('UPDATE receipts SET reversed=1 WHERE reference=?',(reference,))
    elif status in ('refunded','charged_back'):
        conn.execute('UPDATE receipts SET reversed=1 WHERE reference=?',(reference,))
    conn.commit()
    return True


def register_payments(app,brand,prefix,get_db):
    bp=Blueprint(brand+'_payments',__name__)
    @bp.after_request
    def private(response):
        response.headers['Cache-Control']='no-store';return response

    @bp.route('/pagamento/<int:ident>',methods=['GET','POST'])
    def pay(ident):
        user=current_user(brand)
        if not user:return redirect(url_for(brand+'_accounts.login'))
        conn=get_db();row=next((r for r in invoice_rows(conn) if r['id']==ident and r['owner_id']==user['id']),None)
        if not row:abort(404)
        config=settings() if brand=='kaka' else {}
        demo=brand=='sectest' or config.get('test_mode')=='1'
        error=None;payload=None;qr=None
        if request.method=='POST':
            verify_csrf()
            if row['canceled'] or not row['balance']:abort(400,'Cobrança encerrada.')
            action=request.form.get('action')
            token=config.get('mp_access_token','')
            try:
                if demo:raise ValueError('Ambiente de demonstração. A equipe registra a simulação no painel.')
                if not token:raise ValueError('Pagamento por cartão e boleto ainda não configurado.')
                if action=='sync':
                    attempts=conn.execute('SELECT * FROM payment_attempts WHERE invoice_id=?',(ident,)).fetchall()
                    for attempt in attempts:
                        payment=payments.mp_find_payment_for_order(attempt['reference'],token)
                        if payment:apply_payment(conn,payment)
                    return redirect(request.path)
                if action!='checkout':abort(400)
                attempt=conn.execute('SELECT * FROM payment_attempts WHERE invoice_id=? AND amount=? ORDER BY created_at DESC LIMIT 1',(ident,row['balance'])).fetchone()
                if attempt and attempt['checkout_url']:return redirect(attempt['checkout_url'])
                reference='FK'+secrets.token_hex(12)
                conn.execute('INSERT INTO payment_attempts(reference,invoice_id,amount) VALUES (?,?,?)',(reference,ident,row['balance']));conn.commit()
                origin=os.environ.get('PUBLIC_BASE_URL','').rstrip('/')
                if not origin.startswith('https://'):raise ValueError('A equipe precisa configurar PUBLIC_BASE_URL com o endereço HTTPS do site.')
                back=origin+url_for(brand+'_payments.pay',ident=ident)
                body={'items':[{'id':str(ident),'title':row['description'],'quantity':1,'unit_price':row['balance']/100,'currency_id':'BRL'}],
                  'payer':{'email':user['email']},'external_reference':reference,'statement_descriptor':'FK KAKA',
                  'back_urls':dict(success=back,pending=back,failure=back),'auto_return':'approved',
                  'notification_url':origin+url_for(brand+'_payments.webhook'),
                  'payment_methods':{'installments':3}}
                pref=payments._mp('POST','/checkout/preferences',token,body)
                from urllib.parse import urlsplit
                parsed=urlsplit(pref.get('init_point',''))
                if parsed.scheme!='https' or not (parsed.hostname or '').endswith('.mercadopago.com.br'):
                    raise ValueError('Resposta inválida do provedor.')
                conn.execute('UPDATE payment_attempts SET preference=?,checkout_url=? WHERE reference=?',(pref['id'],pref['init_point'],reference));conn.commit()
                return redirect(pref['init_point'])
            except (payments.PaymentError,ValueError):
                error='Não foi possível concluir esta operação. Confira a configuração de pagamento com a equipe e tente novamente.'
        if row['balance'] and not row['canceled']:
            if demo:payload='DEMONSTRACAO-'+brand+'-'+str(ident)
            elif config.get('pix_key'):
                payload=payments.pix_for_order(config,'FK'+str(ident),row['balance']/100)
            if payload:qr=payments.qr_svg(payload)
        return render_template('finance/payment.html',brand=brand,brand_name='FK Káka Autodetail' if brand=='kaka' else 'SecTest',admin=False,
          title='Pagamento',row=row,money=money,qr=qr,payload=payload,demo=demo,mp=bool(config.get('mp_access_token')) and not demo,error=error)

    @bp.post('/webhook/pagamentos')
    def webhook():
        if brand!='kaka':abort(404)
        config=settings();token=config.get('mp_access_token')
        if not token or config.get('test_mode')=='1':return '',200
        data=request.get_json(silent=True) or {}
        if not isinstance(data,dict) or not isinstance(data.get('data',{}),dict):return '',400
        ident=request.args.get('data.id') or (data.get('data') or {}).get('id')
        if not str(ident).isdigit():return '',200
        secret=os.environ.get('FK_MP_WEBHOOK_SECRET')
        if secret:
            parts=dict(part.strip().split('=',1) for part in request.headers.get('x-signature','').split(',') if '=' in part)
            timestamp=parts.get('ts','');signature=parts.get('v1','');request_id=request.headers.get('x-request-id','')
            manifest=f'id:{str(ident).lower()};request-id:{request_id};ts:{timestamp};'
            expected=hmac.new(secret.encode(),manifest.encode(),hashlib.sha256).hexdigest()
            if not timestamp or not request_id or not hmac.compare_digest(expected,signature):return '',401
        # O corpo recebido nunca autoriza crédito: o servidor consulta o provedor
        # autenticado e valida referência, moeda e valor antes de registrar.
        try:apply_payment(get_db(),payments.mp_get_payment(ident,token))
        except payments.PaymentError:return '',503
        return '',200

    app.register_blueprint(bp,url_prefix=prefix)
