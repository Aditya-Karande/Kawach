async function send(message){return chrome.runtime.sendMessage(message)}
function count(events,type){return events.filter(e=>e.eventType===type).length}
async function refresh(){
  const r=await send({type:'GET_STATUS'}); const all=await send({type:'GET_EVENTS',limit:500}); if(!r?.ok)return;
  const s=r.settings, ev=all?.events||r.recentEvents||[];
  document.getElementById('toggle').checked=s.monitoringEnabled;
  document.getElementById('statusText').textContent=s.monitoringEnabled?'ON':'PAUSED';
  document.getElementById('statusHint').textContent=s.monitoringEnabled?'Approved activity is being recorded locally.':'Monitoring is paused. No new events are recorded.';
  document.getElementById('uploads').textContent=count(ev,'file_upload');
  document.getElementById('downloads').textContent=count(ev,'file_download');
  document.getElementById('searches').textContent=count(ev,'search');
  document.getElementById('visits').textContent=count(ev,'page_visit');
  document.getElementById('pending').textContent=r.pendingCount;
  document.getElementById('backend').textContent=s.backendEnabled?(s.backendBaseUrl?'Configured':'Enabled, no URL'):'Not connected';
}
document.getElementById('toggle').addEventListener('change',async e=>{const {settings}=await send({type:'GET_STATUS'}); const next={...settings,monitoringEnabled:e.target.checked}; await chrome.storage.local.set({settings:next}); refresh()});
document.getElementById('settings').onclick=()=>chrome.runtime.openOptionsPage();
document.getElementById('activity').onclick=()=>chrome.tabs.create({url:chrome.runtime.getURL('src/dashboard/dashboard.html')});
document.getElementById('sync').onclick=async()=>{const b=document.getElementById('backend');b.textContent='Syncing…';const r=await send({type:'SYNC_NOW'});b.textContent=r?.result?.success?'Synced':'Not connected';refresh()};
refresh();
