"""Navegação compartilhada, entrada autenticada e sino por contexto de empresa."""
from flask import jsonify, redirect, render_template, request, url_for
from accounts import current_user


def menu(brand):
    def item(endpoint,label,**params):
        return dict(url=url_for(endpoint,**params),label=label,active=request.endpoint==endpoint)
    overview=[item(brand+'.admin_dashboard','Visão geral')]
    if brand=='kaka':
        content=[item('kaka.'+e,t) for e,t in [('admin_services','Serviços e preços'),('admin_pages','Páginas'),('admin_images','Imagens'),('admin_settings','Dados da empresa')]]
        support=[item('kaka.admin_requests','Solicitações antigas'),item('kaka_portal.admin_list','Agendamentos e conversas')]
    else:
        content=[item('sectest_plans.admin_plans','Planos e preços')]
        support=[item('sectest.admin_dashboard','Cadastros e contatos'),item('sectest_portal.admin_list','Solicitações e conversas')]
        support[0]['url']+='#cadastros'
        support[0]['active']=False
    finance=[item(brand+'_finance.dashboard','Faturamento e cobranças'),item(brand+'_finance.dashboard','Exportações CSV / XLSX')]
    finance[1]['url']+='#exportacoes';finance[1]['active']=False
    if brand=='sectest':finance.append(item('sectest_plans.contracts','Contratos mensais'))
    groups=[('Visão geral',overview),('Conteúdo',content),('Atendimento',support),('Financeiro',finance)]
    endpoint=request.endpoint or ''
    if endpoint==brand+'_portal.admin_detail':support[-1]['active']=True
    if endpoint in {brand+'_finance.invoice',brand+'_finance.request_invoices'}:finance[0]['active']=True
    return [dict(label=label,items=items,open=any(i['active'] for i in items)) for label,items in groups]


def init_brand_ui(app, brands):
    app.jinja_env.globals['admin_menu']=menu
    def brand_for_request():
        name=(request.blueprint or '').split('.')[0]
        return next((b for b in brands if name==b or name.startswith(b+'_')),None)

    @app.before_request
    def require_entry_login():
        brand=brand_for_request()
        if not brand or request.endpoint is None:return
        endpoint=request.endpoint
        if endpoint.startswith(brand+'_accounts.') or endpoint in {
            brand+'.static',brand+'_payments.webhook',brand+'.csrf'}:return
        # SecTest serve CSS/JS pela mesma rota curinga que serve as páginas.
        if brand=='sectest' and endpoint=='sectest.page' and request.view_args.get('filename') in {'style.css','script.js','favicon.svg'}:return
        # Os administradores continuam usando somente as guardas administrativas.
        if '/admin' in request.path:return
        if current_user(brand) or current_user(brand,True):return
        login=url_for(brand+'_accounts.login',next=request.full_path.rstrip('?'))
        if request.method not in ('GET','HEAD') or '/api/' in request.path or endpoint.endswith('.messages') or '_notifications.' in endpoint:
            return jsonify(error='Entre na sua conta para continuar.',login_url=login),401
        return redirect(login)

    @app.after_request
    def add_notification_bell(response):
        brand=brand_for_request()
        if not brand or response.status_code!=200 or response.mimetype!='text/html':return response
        if request.endpoint.startswith(brand+'_accounts.'):return response
        admin=('/admin' in request.path or (request.endpoint==brand+'_finance.request_invoices' and current_user(brand,True)))
        if not current_user(brand,admin):return response
        response.direct_passthrough=False
        html=response.get_data(as_text=True)
        if '</body>' in html:
            html=html.replace('</body>',render_template('shared/notifications.html',notification_brand=brand,notification_admin=admin)+'</body>')
            response.set_data(html)
            response.headers.pop('ETag',None)
            response.headers['Cache-Control']='no-store'
        return response
