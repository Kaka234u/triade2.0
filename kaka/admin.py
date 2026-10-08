import json
import math
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from flask import abort, jsonify, redirect, render_template, request, url_for
from PIL import Image, UnidentifiedImageError
from accounts import current_user, require_admin
from .routes import app, get_db, BASE_DIR
from .content import get_business, get_services, safe_url, page_key

def audit(action):
    get_db().execute('INSERT INTO content_history (actor,action) VALUES (?,?)',(current_user('kaka',True)['email'],action))

def pages():
    entries=[('home','Início'),('services_page','Serviços'),('gallery','Galeria'),('about','Sobre'),('contact','Contato'),('faq','Perguntas frequentes'),('quote','Orçamento'),('booking','Agendamento')]
    result=[(url_for('kaka.'+endpoint),name) for endpoint,name in entries]
    result += [(url_for('kaka.policy',kind=kind),name) for kind,name in [('privacidade','Privacidade'),('agendamento','Política de agendamento'),('cancelamento','Cancelamento')]]
    result += [(url_for('kaka.service_detail',slug=s['slug']),s['name']) for s in get_services()]
    return result

@app.get('/admin')
@require_admin('kaka')
def admin_dashboard():
    conn=get_db()
    counts={'Serviços':len(get_services()), 'Orçamentos':conn.execute('SELECT count(*) FROM quote_requests').fetchone()[0], 'Agendamentos':conn.execute('SELECT count(*) FROM booking_requests').fetchone()[0]}
    history=conn.execute('SELECT * FROM content_history ORDER BY id DESC LIMIT 15').fetchall()
    return render_template('kaka/admin/dashboard.html',title='Visão geral',counts=counts,history=history)

@app.route('/admin/servicos',methods=['GET','POST'])
@require_admin('kaka')
def admin_services():
    error=None
    if request.method=='POST':
        form=request.form
        slug=form.get('slug','')
        try:
            if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',slug) or len(slug)>100: raise ValueError('Use um endereço com letras minúsculas, números e hífens.')
            entry={k:form.get(k,'').strip()[:4000] for k in ['name','eyebrow','summary','description','objective','number']}
            if any(not entry[k] for k in ['name','summary','description']): raise ValueError('Preencha nome, resumo e descrição.')
            entry['slug']=slug
            entry['image_url']=form.get('image_url','').strip()
            if entry['image_url'] and not safe_url(entry['image_url'],image=True): raise ValueError('Use um endereço de imagem válido.')
            for key in ['price_min','price_max']:
                entry[key]=float(form.get(key,'').replace(',','.'))
                if not math.isfinite(entry[key]) or not 0<=entry[key]<=1000000: raise ValueError('Preço inválido.')
            if entry['price_max']<entry['price_min']: raise ValueError('O preço máximo não pode ser menor que o mínimo.')
            for key in ['steps','benefits','aftercare']:
                entry[key]=[s.strip() for s in form.get(key,'').splitlines() if s.strip()][:30]
            entry['faq']=[]
            for line in form.get('faq','').splitlines():
                if not line.strip(): continue
                if '|' not in line: raise ValueError('Separe cada pergunta e resposta por |.')
                question,answer=line.split('|',1)
                entry['faq'].append({'question':question.strip(),'answer':answer.strip()})
            position=int(form.get('position','0'))
            exists=get_db().execute('SELECT 1 FROM site_services WHERE slug=?',(slug,)).fetchone()
            if form.get('new')=='1' and exists: raise ValueError('Este endereço já pertence a um serviço.')
            get_db().execute('''INSERT INTO site_services VALUES (?,?,?,?) ON CONFLICT(slug) DO UPDATE SET data=excluded.data,position=excluded.position,active=excluded.active''',
                (slug,json.dumps(entry,ensure_ascii=False),position,int(form.get('active')=='on')))
            audit('Serviço atualizado: '+entry['name']);get_db().commit()
            return redirect(url_for('kaka.admin_services',saved=1))
        except (ValueError,TypeError) as exc:
            error=str(exc) or 'Revise os campos.'
    return render_template('kaka/admin/services.html',title='Serviços e preços',items=get_services(True),error=error),400 if error else 200

@app.route('/admin/configuracoes',methods=['GET','POST'])
@require_admin('kaka')
def admin_settings():
    error=None
    values=get_business()
    labels={'name':'Nome da empresa','email':'E-mail','phone':'Telefone exibido','whatsapp_number':'WhatsApp com país e DDD (somente números)',
      'address_line':'Rua e número','district_city':'Bairro, cidade e estado','postal_code':'CEP','weekday_hours':'Horário de segunda a sexta','weekend_hours':'Horário de fim de semana',
      'instagram_url':'Endereço do Instagram','instagram_label':'Nome exibido do Instagram','hero_image':'Imagem principal (URL ou arquivo enviado)','page_image':'Imagem de fundo das páginas'}
    if request.method=='POST':
        values={k:request.form.get(k,'').strip()[:1000] for k in labels}
        if any(not value for value in values.values()): error='Preencha todos os campos.'
        elif not re.fullmatch(r'\d{10,15}',values['whatsapp_number']): error='Informe WhatsApp com país e DDD, somente números.'
        elif not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',values['email']): error='Informe um e-mail válido.'
        elif any(not safe_url(values[k],True) for k in ['hero_image','page_image']) or not safe_url(values['instagram_url']): error='Use URLs HTTPS ou caminhos locais válidos.'
        if not error:
            # Caminhos internos permanecem portáveis entre /kaka e domínio próprio.
            prefix=url_for('kaka.static',filename='')
            for key in ['hero_image','page_image']:
                if values[key].startswith(prefix): values[key]='static/'+values[key][len(prefix):]
            get_db().execute("UPDATE site_settings SET value=? WHERE key='business'",(json.dumps(values,ensure_ascii=False),))
            audit('Dados da empresa atualizados');get_db().commit()
            return redirect(url_for('kaka.admin_settings',saved=1))
    return render_template('kaka/admin/settings.html',title='Dados da empresa',values=values,labels=labels,error=error),400 if error else 200

@app.get('/admin/paginas')
@require_admin('kaka')
def admin_pages():
    return render_template('kaka/admin/pages.html',title='Editar páginas',pages=pages())

@app.route('/admin/solicitacoes',methods=['GET','POST'])
@require_admin('kaka')
def admin_requests():
    if request.method=='POST' and request.form.get('kind')=='booking':
        linked=get_db().execute('SELECT id FROM client_requests WHERE source_id=?',(request.form.get('id'),)).fetchone()
        if linked:
            return redirect(url_for('kaka_portal.admin_detail',ident=linked['id']))
    statuses={'new':'Novo','pending_manual_confirmation':'Aguardando confirmação','contacted':'Em atendimento','confirmed':'Confirmado','completed':'Concluído','cancelled':'Cancelado'}
    if request.method=='POST':
        table={'quote':'quote_requests','booking':'booking_requests'}.get(request.form.get('kind'))
        status=request.form.get('status')
        if not table or status not in statuses: abort(400)
        cur=get_db().execute(f'UPDATE {table} SET status=? WHERE id=?',(status,request.form.get('id')))
        if not cur.rowcount: abort(404)
        audit('Atendimento atualizado: '+request.form['id']);get_db().commit()
        return redirect(url_for('kaka.admin_requests',saved=1))
    return render_template('kaka/admin/requests.html',title='Orçamentos e agendamentos',statuses=statuses,
       quotes=get_db().execute('SELECT * FROM quote_requests ORDER BY created_at DESC').fetchall(),
       bookings=get_db().execute('SELECT * FROM booking_requests ORDER BY created_at DESC').fetchall())

@app.route('/admin/imagens',methods=['GET','POST'])
@require_admin('kaka')
def admin_images():
    error=None
    folder=BASE_DIR/'static'/'uploads';folder.mkdir(exist_ok=True)
    if request.method=='POST':
        upload=request.files.get('image')
        try:
            if not upload: raise ValueError('Selecione uma imagem.')
            picture=Image.open(upload.stream)
            if picture.width*picture.height>24000000: raise ValueError('Use uma imagem de até 24 megapixels.')
            picture.load()
            picture.thumbnail((3000,3000))
            filename=uuid.uuid4().hex+'.webp'
            picture.convert('RGB').save(folder/filename,'WEBP',quality=88)
            audit('Imagem enviada: '+filename);get_db().commit()
            return redirect(url_for('kaka.admin_images',saved=1))
        except (ValueError,UnidentifiedImageError,OSError,Image.DecompressionBombError):
            error='Envie uma imagem PNG, JPEG ou WebP válida de até 8 MB e 24 megapixels.'
    images=[url_for('kaka.static',filename='uploads/'+f.name) for f in sorted(folder.glob('*.webp'),key=lambda f:f.stat().st_mtime,reverse=True)]
    return render_template('kaka/admin/images.html',title='Biblioteca de imagens',images=images,error=error),400 if error else 200

@app.post('/admin/api/conteudo')
@require_admin('kaka')
def admin_save_content():
    body=request.get_json(silent=True)
    if not isinstance(body,dict): abort(400)
    page=body.get('page','')
    if page not in dict(pages()): abort(400)
    page=page_key(page)
    changes=body.get('changes',{})
    if not isinstance(changes,dict) or len(changes)>1000: abort(400)
    for key,value in changes.items():
        if not re.fullmatch(r'(text|src|alt|href|content):(shared|page):[a-f0-9]{24}',key) or not isinstance(value,str) or len(value)>8000: abort(400)
        if key.startswith(('src:','href:')) and not safe_url(value,key.startswith('src:')): abort(400,'Endereço inválido.')
    if body.get('reset') is True:
        get_db().execute('DELETE FROM page_edits WHERE page=?',(page,))
    else:
        for key,value in changes.items():
            get_db().execute('INSERT INTO page_edits VALUES (?,?,?) ON CONFLICT(page,field) DO UPDATE SET value=excluded.value',('*' if ':shared:' in key else page,key,value))
    audit(('Conteúdo restaurado: ' if body.get('reset') else 'Conteúdo editado: ')+page)
    get_db().commit()
    return jsonify(ok=True)

from . import editor
