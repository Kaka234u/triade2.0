(() => {
  const box=document.querySelector('[data-chat-url]');if(!box)return;
  const form=document.querySelector('[data-chat-form]'), status=document.querySelector('[data-chat-status]');
  let busy=false,sending=false,last=Number(box.dataset.lastId||0);
  const nearBottom=()=>box.scrollHeight-box.scrollTop-box.clientHeight<90;
  async function refresh(){
    if(busy||document.hidden)return;busy=true;
    try{
      const url=new URL(box.dataset.chatUrl,location.origin);url.searchParams.set('after',last);
      const response=await fetch(url,{cache:'no-store'});
      if(response.status===401){status.textContent='Sua sessão expirou. Entre novamente; seu texto permanece aqui.';return;}
      if(!response.ok)return;const data=await response.json();if(!data.messages.length)return;
      const stick=nearBottom(),oldScroll=box.scrollTop;
      box.querySelector('[data-chat-empty]')?.remove();
      for(const m of data.messages){
        if(m.id<=last)continue;
        const article=document.createElement('article');article.className='message '+(m.administrator?'staff':'client');article.dataset.messageId=m.id;
        const author=document.createElement('strong');author.textContent=m.administrator?'Administrador':'Cliente';
        const time=document.createElement('small');time.textContent=m.created_at+' UTC';
        const body=document.createElement('p');body.className='preserve-lines';body.textContent=m.body;
        article.append(author,time,body);box.append(article);last=m.id;
      }
      box.scrollTop=stick?box.scrollHeight:oldScroll;
      window.dispatchEvent(new Event('notifications:refresh'));
    }catch(_){status.textContent='Conexão interrompida. Seu texto foi mantido.';}finally{busy=false;}
  }
  form.addEventListener('submit',async e=>{
    e.preventDefault();if(sending||!form.reportValidity())return;
    const input=form.elements.message,value=input.value,button=form.querySelector('button');sending=true;button.disabled=true;status.textContent='Enviando…';
    try{const r=await fetch(form.action||location.href,{method:'POST',headers:{Accept:'application/json'},body:new FormData(form)});const data=await r.json().catch(()=>({error:'Sessão expirada ou resposta indisponível. Seu texto foi mantido.'}));if(!r.ok||!data.ok)throw new Error(data.error||'Não foi possível enviar.');if(input.value===value)input.value='';status.textContent='Mensagem enviada.';await refresh();}
    catch(error){status.textContent=error.message||'Não foi possível enviar. Seu texto foi mantido.';}
    finally{sending=false;button.disabled=false;}
  });
  setInterval(refresh,10000);document.addEventListener('visibilitychange',refresh);refresh();
})();
