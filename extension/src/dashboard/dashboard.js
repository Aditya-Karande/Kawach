let events=[];
const labels={page_visit:'Website visit',search:'Search query',file_upload:'File uploaded',file_download:'File downloaded',form_submission:'Form submitted',page_metadata:'Page metadata'};
function count(t){return events.filter(e=>e.eventType===t).length}
function esc(v){return String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]))}
function render(){
  const q=document.getElementById('q').value.toLowerCase();const type=document.getElementById('type').value;
  document.getElementById('uploads').textContent=count('file_upload');document.getElementById('downloads').textContent=count('file_download');document.getElementById('searches').textContent=count('search');document.getElementById('visits').textContent=count('page_visit');document.getElementById('forms').textContent=count('form_submission');
  const visible=events.filter(e=>(type==='all'||e.eventType===type)&&JSON.stringify(e).toLowerCase().includes(q));
  document.getElementById('list').innerHTML=visible.map(e=>{const d=e.data||{}; const domain=d.domain||d.actionDomain||''; const entries=Object.entries(d).filter(([k])=>!['pageUrl','domain','pageTitle'].includes(k)); return `<article class="event"><div class="eventhead"><span class="badge">${esc(labels[e.eventType]||e.eventType)}</span><span class="time">${esc(new Date(e.timestamp).toLocaleString())}</span></div><div class="domain">${esc(domain||d.pageUrl||'—')}</div><div class="details">${entries.slice(0,10).map(([k,v])=>`<span class="key">${esc(k)}</span><span class="mono">${esc(typeof v==='object'?JSON.stringify(v):v)}</span>`).join('')}</div></article>`}).join('')||'<div class="event">No matching activity.</div>';
}
async function load(){const r=await chrome.runtime.sendMessage({type:'GET_EVENTS',limit:500});events=r?.events||[];render()}
document.getElementById('refresh').onclick=load;document.getElementById('q').oninput=render;document.getElementById('type').onchange=render;document.getElementById('clear').onclick=async()=>{if(confirm('Delete all locally stored activity?')){await chrome.runtime.sendMessage({type:'CLEAR_EVENTS'});load()}};load();
