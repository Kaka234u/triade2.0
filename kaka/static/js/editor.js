(() => {
  const config = JSON.parse(document.getElementById('fk-editor-data').textContent);
  const fields = config.fields, changes = {};
  const dialog = document.getElementById('fk-modal'), select = document.getElementById('fk-field');
  const value = document.getElementById('fk-value'), status = document.getElementById('fk-editor-status');
  let busy = false;
  const read = key => changes[key] ?? fields[key].value;
  const all=document.createElement('select');
  all.setAttribute('aria-label','Escolher qualquer campo da página');
  all.style.cssText='max-width:260px;background:#151a21;color:white;padding:10px;border:1px solid #657182';
  const placeholder=document.createElement('option');placeholder.textContent='Todos os campos (inclui título e SEO)';placeholder.value='';all.append(placeholder);
  Object.entries(fields).forEach(([key,field])=>{const option=document.createElement('option');option.value=key;option.textContent=field.label+': '+field.value.trim().slice(0,75);all.append(option);});
  document.getElementById('fk-editor').insertBefore(all,document.getElementById('fk-save'));
  all.onchange=()=>{if(!all.value)return;select.replaceChildren();const option=document.createElement('option');option.value=all.value;option.textContent=fields[all.value].label;select.append(option);value.value=read(all.value);dialog.showModal();value.focus();all.value='';};
  document.addEventListener('click', event => {
    if (event.target.closest('#fk-editor,#fk-modal')) return;
    const el = event.target.closest('[data-fk-edit],[data-fk-src],[data-fk-href]');
    if (!el) return;
    event.preventDefault(); event.stopImmediatePropagation();
    const keys = new Set();
    [el, el.closest('a')].filter(Boolean).forEach(node => {
      ['edit','src','alt','href'].forEach(attr => { const key=node.getAttribute('data-fk-'+attr); if(key) keys.add(key); });
    });
    select.replaceChildren();
    keys.forEach(key => { const option=document.createElement('option'); option.value=key; option.textContent=fields[key].label; select.append(option); });
    value.value=read(select.value); dialog.showModal(); value.focus();
  }, true);
  select.addEventListener('change', () => value.value=read(select.value));
  document.getElementById('fk-cancel').onclick=()=>dialog.close();
  document.getElementById('fk-apply').onclick=()=>{
    const key=select.value, next=value.value, type=key.split(':')[0];
    if (['src','href'].includes(type)) {
      let parsed; try {parsed=new URL(next,location.href);} catch {alert('Endereço inválido.');return;}
      const protocols=type==='src'?['https:']:['https:','mailto:','tel:'];
      if (!protocols.includes(parsed.protocol) && !(parsed.origin===location.origin && next.startsWith('/'))) {alert('Use HTTPS ou um caminho local começando com /.');return;}
    }
    changes[key]=next;
    const attr=type==='text'?'edit':type;
    document.querySelectorAll('[data-fk-'+attr+']').forEach(node=>{
      if(node.getAttribute('data-fk-'+attr)!==key) return;
      if(type==='text') node.textContent=next; else node.setAttribute(type,next);
    });
    status.textContent=Object.keys(changes).length+' alteração(ões) pendente(s)'; dialog.close();
  };
  async function save(reset=false) {
    if(busy) return;
    busy=true;status.textContent='Salvando…';
    try {
      const response=await fetch(config.saveUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':config.csrf},body:JSON.stringify({page:config.page,changes,reset})});
      if(!response.ok) throw new Error(response.status===401?'Sua sessão expirou. Entre novamente.':'Não foi possível salvar. Revise os endereços e tente novamente.');
      Object.keys(changes).forEach(key=>delete changes[key]); location.reload();
    } catch(error) {status.textContent=error.message;} finally {busy=false;}
  }
  document.getElementById('fk-save').onclick=()=>save();
  document.getElementById('fk-reset').onclick=()=>{if(confirm('Restaurar os textos e imagens desta página? As edições compartilhadas do cabeçalho e rodapé serão mantidas.')) save(true);};
  window.addEventListener('beforeunload',event=>{if(Object.keys(changes).length){event.preventDefault();event.returnValue='';}});
})();
