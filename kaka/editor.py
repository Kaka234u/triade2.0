"""Edição de texto puro e atributos seguros; nunca executa HTML ou Jinja salvo."""
import hashlib
from bs4 import BeautifulSoup, Comment, NavigableString
from flask import render_template, request, url_for
from accounts import current_user
from .routes import app, get_db
from .content import get_business, page_key
from .data import business as original_business

EXCLUDED = {'script','style','svg','textarea','select','option','input'}

def field_key(kind, value, shared):
    return kind+':'+('shared' if shared else 'page')+':'+hashlib.sha256(value.encode()).hexdigest()[:24]

@app.after_request
def apply_content(response):
    if request.path.find('/admin')>=0:
        response.headers['Cache-Control']='no-store'
        response.headers['X-Robots-Tag']='noindex, nofollow'
        return response
    if response.status_code!=200 or response.mimetype!='text/html' or request.endpoint=='kaka.static':
        return response
    editing = request.args.get('editar')=='1' and bool(current_user('kaka',True))
    # Os arquivos de autenticação usam outro blueprint e não passam neste editor.
    soup=BeautifulSoup(response.get_data(as_text=True),'html.parser')
    edits={row['field']:row['value'] for row in get_db().execute('SELECT field,value FROM page_edits WHERE page IN (?,?)',('*',page_key(request.path)))}
    business=get_business()
    replacements={old:business[key] for key,old in original_business.items() if old and old!=business.get(key)}
    fields={}
    for node in list(soup.find_all(string=True)):
        if isinstance(node,Comment) or not node.strip() or not node.parent or node.find_parent(list(EXCLUDED)):
            continue
        if node.find_parent(class_='service-price'): continue
        original=str(node)
        current=original
        for old,new in replacements.items(): current=current.replace(old,new)
        shared=bool(node.find_parent(['header','footer']))
        key=field_key('text',original,shared)
        value=edits.get(key,current)
        if editing and node.parent.name=='title':
            node.parent['data-fk-edit']=key
            fields[key]={'value':value,'label':'Título da página (aba do navegador)'}
        if editing and node.find_parent('body'):
            span=soup.new_tag('span')
            span['data-fk-edit']=key
            span.string=value
            node.replace_with(span)
            fields[key]={'value':value,'label':'Texto'+(' (cabeçalho/rodapé de todas as páginas)' if shared else '')}
        elif value!=original:
            node.replace_with(NavigableString(value))
    for tag in soup.find_all(['img','a','meta']):
        if tag.name=='meta' and tag.get('name')!='description': continue
        attrs=['src','alt'] if tag.name=='img' else (['content'] if tag.name=='meta' else ['href'])
        shared=bool(tag.find_parent(['header','footer']))
        for attr in attrs:
            original=tag.get(attr)
            if not original: continue
            if attr=='href' and not original.startswith(('https://','mailto:','tel:')): continue
            key=field_key(attr,original,shared)
            value=edits.get(key,original)
            tag[attr]=value
            if tag.name=='img' and attr=='src':
                parent=tag.find_parent(attrs={'data-src':True})
                if parent: parent['data-src']=value
            if editing:
                tag['data-fk-'+attr]=key
                fields[key]={'value':value,'label':{'src':'Endereço da imagem','alt':'Descrição da imagem','href':'Destino do link','content':'Descrição para mecanismos de busca'}[attr]}
    if editing:
        toolbar=BeautifulSoup(render_template('kaka/admin/editor.html',fields=fields),'html.parser')
        soup.body.append(toolbar)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Robots-Tag']='noindex, nofollow'
    response.set_data(str(soup))
    return response
