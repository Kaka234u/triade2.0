(() => {
  const root=document.querySelector('[data-notifications-url]');if(!root)return;
  const toggle=root.querySelector('.notification-toggle'), panel=root.querySelector('.notification-panel'), count=root.querySelector('[data-notification-count]'), list=root.querySelector('[data-notification-items]'),status=root.querySelector('[data-notification-status]');
  let busy=false,latest=0,signature='';
  function render(data){
    latest=data.latest;count.textContent=data.unread>99?'99+':data.unread;count.hidden=!data.unread;
    toggle.setAttribute('aria-label',`Notificações: ${data.unread} não lidas`);
    status.textContent=data.items.length?'':'Nenhuma notificação.';
    const next=JSON.stringify(data.items);if(next===signature)return;signature=next;
    const focusId=document.activeElement?.dataset?.readId;
    list.replaceChildren(...data.items.map(item=>{
      const li=document.createElement('li');li.className=item.read_at?'':'unread';
      const a=document.createElement('a');a.href=item.url;a.textContent=item.title;
      const p=document.createElement('p');p.textContent=item.body;
      const time=document.createElement('small');time.textContent=item.created_at+' UTC';li.append(a,p,time);
      if(!item.read_at){const b=document.createElement('button');b.type='button';b.textContent='Marcar como lida';b.dataset.readId=item.id;b.addEventListener('click',()=>mark({id:item.id}));li.append(b);}return li;
    }));
    if(focusId){const target=list.querySelector(`[data-read-id="${focusId}"]`);(target||root.querySelector('[data-read-all]')).focus({preventScroll:true});}
  }
  async function refresh(){if(busy||document.hidden)return;busy=true;try{const r=await fetch(root.dataset.notificationsUrl,{cache:'no-store'});if(r.status===401){status.textContent='Sua sessão expirou. Entre novamente.';return;}if(r.ok)render(await r.json());}catch(_){status.textContent='Sem conexão. Tentaremos novamente.';}finally{busy=false;}}
  async function mark(body){try{const r=await fetch(root.dataset.readUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':root.dataset.csrf},body:JSON.stringify(body)});if(r.ok)render(await r.json());else status.textContent='Não foi possível marcar. Atualize sua sessão.';}catch(_){status.textContent='Sem conexão. Tente novamente.';}}
  toggle.addEventListener('click',()=>{panel.hidden=!panel.hidden;toggle.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden)refresh();});
  root.querySelector('[data-read-all]').addEventListener('click',()=>mark({all:true,through:latest}));
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden){panel.hidden=true;toggle.setAttribute('aria-expanded','false');toggle.focus();}});
  document.addEventListener('visibilitychange',refresh);setInterval(refresh,10000);window.addEventListener('notifications:refresh',refresh);refresh();
})();
