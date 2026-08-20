const ids=['collectVisits','collectSearches','collectChatMessages','collectUploads','collectDownloads','collectForms','collectPageMetadata','collectPageText','pageTextMaxChars','urlMode','protectSensitiveSites','excludedDomains','backendEnabled','backendBaseUrl','backendSignalsPath','backendEventsPath','childId'];
const defaults={monitoringEnabled:true,collectVisits:true,collectSearches:true,collectChatMessages:true,collectUploads:true,collectDownloads:true,collectForms:true,collectPageMetadata:true,collectPageText:false,pageTextMaxChars:2000,urlMode:'domain',protectSensitiveSites:true,excludedDomains:[],backendEnabled:false,backendBaseUrl:'',backendSignalsPath:'/api/signals',backendEventsPath:'/api/events',childId:'child_001'};

async function load(){
  const {settings={}}=await chrome.storage.local.get('settings');
  const s={...defaults,...settings};
  for(const id of ids){
    const el=document.getElementById(id);
    if(el.type==='checkbox') el.checked=!!s[id];
    else if(id==='excludedDomains') el.value=s[id].join(', ');
    else el.value=s[id];
  }
}

async function save(){
  const {settings={}}=await chrome.storage.local.get('settings');
  const next={...settings};
  for(const id of ids){
    const el=document.getElementById(id);
    if(el.type==='checkbox') next[id]=el.checked;
    else if(id==='excludedDomains') next[id]=el.value.split(',').map(x=>x.trim().toLowerCase()).filter(Boolean);
    else if(id==='pageTextMaxChars') next[id]=Math.max(100,Math.min(10000,Number(el.value)||2000));
    else next[id]=el.value;
  }
  await chrome.storage.local.set({settings:next});
  document.getElementById('saved').textContent='Settings saved.';
  setTimeout(()=>document.getElementById('saved').textContent='',1800);
}

async function pair(){
  const codeEl=document.getElementById('pairingCode');
  const statusEl=document.getElementById('pairStatus');
  const code=codeEl.value.trim();
  if(!code){ statusEl.textContent='Enter a pairing code first.'; return; }
  statusEl.textContent='Pairing…';
  const response=await chrome.runtime.sendMessage({type:'PAIR_DEVICE', pairingCode: code});
  const result=response?.result;
  if(result?.success && result.child_id){
    statusEl.textContent=`Paired. This device is now linked as ${result.child_id}.`;
    codeEl.value='';
    await load();
  } else {
    statusEl.textContent=`Pairing failed: ${result?.error || 'unknown error'}`;
  }
}

document.getElementById('save').onclick=save;
document.getElementById('pairBtn').onclick=pair;
load();
