(() => {
  const box=document.querySelector('[data-chat-url]');if(!box)return;
  let signature='';
  async function refresh(){
    if(document.hidden)return;
    try{
      const response=await fetch(box.dataset.chatUrl,{cache:'no-store'});
      if(!response.ok)return;
      const data=await response.json(), next=JSON.stringify(data.messages);
      if(signature===next)return;signature=next;
      const nodes=data.messages.map(message=>{
        const article=document.createElement('article');article.className='message '+(message.administrator?'staff':'client');
        const author=document.createElement('strong');author.textContent=message.administrator?'Administrador':'Cliente';
        const time=document.createElement('small');time.textContent=message.created_at+' UTC';
        const body=document.createElement('p');body.className='preserve-lines';body.textContent=message.body;
        article.append(author,time,body);return article;
      });box.replaceChildren(...nodes);box.scrollTop=box.scrollHeight;
    }catch(_){/* Histórico permanece disponível quando a rede falha. */}
  }
  setInterval(refresh,10000);refresh();
})();
