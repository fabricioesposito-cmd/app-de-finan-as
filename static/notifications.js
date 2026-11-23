'use strict';
(()=>{
 const button=document.createElement('button');button.type='button';button.id='notifications-button';button.textContent='Notificações';
 document.querySelector('.topbar-actions').prepend(button);
 const dialog=document.createElement('dialog');dialog.id='notifications-dialog';
 dialog.innerHTML='<div class="dialog-header"><div><p class="eyebrow">CLAREZA NO SEU DIA</p><h2>Resumo diário</h2></div><button type="button" aria-label="Fechar">×</button></div><p>Receba o valor disponível para gastar no mês, após os compromissos, os gastos registrados e a reserva planejada.</p><p class="small muted">O valor aparecerá na notificação do celular e considera os dados cadastrados no Clareza.</p><label>Horário diário (Brasília)<select id="push-hour" aria-label="Horário da notificação"></select></label><p id="push-status" class="info-box" role="status"></p><div class="dialog-actions"><button id="push-disable" type="button" hidden>Desativar neste aparelho</button><button id="push-test" type="button" hidden>Enviar teste</button><button id="push-enable" class="primary" type="button">Ativar neste aparelho</button></div>';
 document.body.append(dialog);
 const get=id=>document.getElementById(id),hour=get('push-hour'),status=get('push-status'),enable=get('push-enable'),disable=get('push-disable'),test=get('push-test');
 for(let n=0;n<24;n++){const option=document.createElement('option');option.value=n;option.textContent=String(n).padStart(2,'0')+':00';hour.append(option);}hour.value='9';
 dialog.querySelector('[aria-label="Fechar"]').onclick=()=>dialog.close();
 let registration=null,subscription=null,saved=null,config=null;
 const installed=()=>matchMedia('(display-mode: standalone)').matches||navigator.standalone;
 const ios=()=>/iPhone|iPad|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
 function paint(){
  const active=!!saved?.enabled;
  enable.textContent=active?'Salvar horário':'Ativar neste aparelho';
  test.hidden=disable.hidden=!active;
  if(saved)hour.value=String(saved.hour);
  status.textContent=active?'Ativado neste aparelho, todos os dias às '+String(saved.hour).padStart(2,'0')+'h (Brasília). A entrega depende da conexão e das permissões do celular.':'Ative para receber seu resumo diário às '+String(hour.value).padStart(2,'0')+'h (Brasília).';
 }
 async function refresh(){
  enable.disabled=true;test.hidden=disable.hidden=true;status.textContent='Verificando as notificações…';
  if(ios()&&!installed()){status.textContent='No iPhone, abra o Clareza pelo ícone da tela inicial. Se ainda não instalou: Safari → Compartilhar → Adicionar à Tela de Início. Requer iOS 16.4 ou superior.';return;}
  if(!isSecureContext||!('serviceWorker' in navigator)||!('PushManager' in window)||!('Notification' in window)){status.textContent='Este navegador não oferece notificações. No iPhone, use o Clareza instalado na tela inicial com iOS 16.4 ou superior.';return;}
  const response=await fetch('/api/push/settings',{cache:'no-store'});config=await response.json();if(!response.ok)throw Error(config.error||'Não foi possível consultar as notificações.');
  if(!config.configured){status.textContent='As notificações ainda não estão disponíveis no servidor. Tente novamente mais tarde.';return;}
  registration=await navigator.serviceWorker.register('/push-sw.js',{scope:'/'});await navigator.serviceWorker.ready;
  subscription=await registration.pushManager.getSubscription();saved=config.subscriptions.find(s=>s.endpoint===subscription?.endpoint)||null;
  paint();
  if(Notification.permission==='denied'){status.textContent='As notificações estão bloqueadas. Libere o Clareza em Ajustes → Notificações no iPhone e abra esta tela novamente.';return;}
  enable.disabled=false;
 }
 button.onclick=()=>{openDialog('notifications-dialog');act(refresh,button);};
 enable.onclick=()=>{
  // Permission must be requested directly from the tap, before any network await.
  const permission=Notification.permission==='default'?Notification.requestPermission():Promise.resolve(Notification.permission);
  act(async()=>{
   if(await permission!=='granted')throw Error('Permita as notificações para ativar o resumo diário.');
   if(!registration||!config)throw Error('Feche esta tela e abra Notificações novamente.');
   if(!subscription){const base64=config.public_key.replace(/-/g,'+').replace(/_/g,'/');const bytes=Uint8Array.from(atob(base64+'='.repeat((4-base64.length%4)%4)),c=>c.charCodeAt(0));subscription=await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:bytes});}
   await api('/api/push/subscribe',{subscription:subscription.toJSON(),hour:Number(hour.value)});
   await refresh();notify('Resumo diário ativado neste aparelho.');
  },enable);
 };
 disable.onclick=()=>act(async()=>{await api('/api/push/disable',{id:saved.id});if(subscription)await subscription.unsubscribe();saved=null;subscription=null;await refresh();notify('Resumo diário desativado neste aparelho.');},disable);
 test.onclick=()=>act(async()=>{await api('/api/push/test',{id:saved.id});status.textContent='Teste enviado. Confira as notificações do celular.';},test);
})();
