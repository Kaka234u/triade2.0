import json
import secrets
from datetime import date
from flask import Blueprint, abort, redirect, render_template, request, url_for
from accounts import current_user, require_admin, verify_csrf
from finance import cents,money
from customer_portal import add_request

DEFAULTS=[('pessoal','Pessoal',3990,'mensal','Orientação sobre contas, senhas e autenticação em duas etapas.'),
 ('pequeno','Pequeno Negócio',14990,'mensal','Revisão básica de configuração de um site e relatório mensal.'),
 ('profissional','Profissional',34990,'mensal','Revisão de até três sites e acompanhamento mensal combinado com a equipe.'),
 ('diagnostico','Diagnóstico avulso',49900,'avulso','Avaliação inicial de riscos e recomendações para um site.'),
 ('empresarial','Empresarial',0,'consulta','Escopo e proposta definidos após análise técnica.')]

def init_plans(conn):
    conn.executescript('''CREATE TABLE IF NOT EXISTS service_plans (
      slug TEXT PRIMARY KEY,name TEXT NOT NULL,price INTEGER NOT NULL,period TEXT NOT NULL,description TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS plan_requests (request_id INTEGER PRIMARY KEY,plan_slug TEXT NOT NULL,
      price INTEGER NOT NULL,period TEXT NOT NULL,answers TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS monthly_issues (request_id INTEGER NOT NULL,month TEXT NOT NULL,invoice_id INTEGER NOT NULL,
      PRIMARY KEY(request_id,month));''')
    conn.executemany('INSERT OR IGNORE INTO service_plans VALUES (?,?,?,?,?)',DEFAULTS)

def estimate(plan,answers):
    if plan['period']=='consulta' or answers['visits']>10000 or answers['people']>200 or answers['revenue']>100000:
        return None
    # Pesos são uma regra comercial inicial explícita, não um diagnóstico de segurança.
    extra=(5000 if answers['attacked'] else 0)+(5000 if answers['sensitive'] else 0)
    extra+=max(0,answers['sites']-(3 if plan['slug']=='profissional' else 1))*3000
    extra+=5000 if answers['visits']>1000 else 0
    return plan['price']+extra

def register_plans(app,get_db):
    bp=Blueprint('sectest_plans',__name__)
    def render(template,**kw):
        return render_template('plans/'+template,brand='sectest',brand_name='SecTest',money=money,**kw)

    @bp.route('/planos',methods=['GET','POST'])
    def plans():
        rows=get_db().execute('SELECT * FROM service_plans ORDER BY price').fetchall()
        return render('plans.html',title='Planos de segurança digital',rows=rows,admin=False)

    @bp.route('/diagnostico',methods=['GET','POST'])
    def diagnostic():
        user=current_user('sectest')
        if not user:return redirect(url_for('sectest_accounts.login'))
        conn=get_db();rows=conn.execute('SELECT * FROM service_plans ORDER BY price').fetchall();error=None;result=None;selected=None
        if request.method=='POST':
            verify_csrf()
            try:
                selected=next((p for p in rows if p['slug']==request.form.get('plan')),None)
                if not selected:raise ValueError('Escolha um plano.')
                answers={k:int(request.form.get(k,'')) for k in ('visits','people','sites','revenue')}
                if any(v<0 or v>100000000 for v in answers.values()) or answers['sites']<1:raise ValueError('Revise as quantidades.')
                answers.update(attacked=request.form.get('attacked')=='sim',sensitive=request.form.get('sensitive')=='sim')
                result=estimate(selected,answers)
                if request.form.get('action')=='submit':
                    ident=add_request(conn,'sectest','ST-'+secrets.token_hex(8),selected['name'],
                        'Visitas/dia: {visits}; usuários: {people}; sites: {sites}; receita mensal com anúncios: R$ {revenue}; ataque anterior: {attacked}; dados sensíveis: {sensitive}'.format(**answers))
                    conn.execute('INSERT INTO plan_requests(request_id,plan_slug,price,period,answers) VALUES (?,?,?,?,?)',
                      (ident,selected['slug'],result or 0,selected['period'],json.dumps(answers)))
                    conn.execute('UPDATE client_requests SET total_cents=? WHERE id=?',(result or 0,ident));conn.commit()
                    return redirect(url_for('sectest_portal.detail',ident=ident))
            except (ValueError,TypeError) as exc:error=str(exc) or 'Revise os campos.'
        return render('diagnostic.html',title='Avaliação inicial',rows=rows,admin=False,error=error,result=result,selected=selected)

    @bp.route('/admin/planos',methods=['GET','POST'])
    @require_admin('sectest')
    def admin_plans():
        conn=get_db();error=None
        if request.method=='POST':
            try:
                price=cents(request.form.get('price',''));period=request.form.get('period')
                name=request.form.get('name','').strip()[:100];description=request.form.get('description','').strip()[:2000]
                if not name or not description or period not in ('mensal','avulso','consulta'):raise ValueError('Preencha todos os campos.')
                conn.execute('UPDATE service_plans SET name=?,price=?,period=?,description=? WHERE slug=?',(name,price,period,description,request.form.get('slug')));conn.commit()
                return redirect(request.path)
            except ValueError as exc:error=str(exc)
        return render('edit.html',title='Planos e preços',rows=conn.execute('SELECT * FROM service_plans ORDER BY price').fetchall(),admin=True,error=error)

    @bp.route('/admin/contratos',methods=['GET','POST'])
    @require_admin('sectest')
    def contracts():
        conn=get_db();error=None
        if request.method=='POST':
            try:
                ident=int(request.form.get('ident',''));contract=conn.execute('SELECT * FROM plan_requests WHERE request_id=?',(ident,)).fetchone()
                if not contract:abort(404)
                if request.form.get('action')=='stop':conn.execute('UPDATE plan_requests SET active=0 WHERE request_id=?',(ident,))
                elif request.form.get('action')=='activate':
                    price=cents(request.form.get('price',''))
                    if price<=0:raise ValueError('Defina o preço combinado antes de ativar.')
                    conn.execute('UPDATE plan_requests SET active=1,price=? WHERE request_id=?',(price,ident))
                    conn.execute('UPDATE client_requests SET total_cents=? WHERE id=?',(price,ident))
                elif request.form.get('action')=='issue':
                    month=request.form.get('month','');due=date.fromisoformat(month+'-10').isoformat()
                    if not contract['active'] or contract['price']<=0:raise ValueError('Ative o contrato com o preço combinado.')
                    conn.execute('BEGIN IMMEDIATE')
                    if not conn.execute('SELECT 1 FROM monthly_issues WHERE request_id=? AND month=?',(ident,month)).fetchone():
                        cursor=conn.execute('INSERT INTO invoices(request_id,description,total,due,reference) VALUES (?,?,?,?,?)',
                          (ident,'Mensalidade '+month,contract['price'],due,'ST-'+str(ident)+'-'+month))
                        conn.execute('INSERT INTO monthly_issues VALUES (?,?,?)',(ident,month,cursor.lastrowid))
                else:abort(400)
                conn.commit();return redirect(request.path)
            except ValueError as exc:conn.rollback();error=str(exc)
        rows=conn.execute("SELECT p.*,r.service FROM plan_requests p JOIN client_requests r ON r.id=p.request_id WHERE p.period='mensal'").fetchall()
        return render('contracts.html',title='Contratos mensais',rows=rows,admin=True,error=error,month=date.today().isoformat()[:7])
    app.register_blueprint(bp,url_prefix='/sectest')
