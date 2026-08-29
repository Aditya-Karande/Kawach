// Monitoring is parent-controlled only (spec Section 4.6). This popup
// never writes settings.monitoringEnabled — it only displays whatever
// the service worker currently has, which itself is kept in sync with
// the backend via CHECK_MONITORING_STATUS / the periodic status-poll
// alarm in service-worker.js. There is no toggle here on purpose.
async function send(message){return chrome.runtime.sendMessage(message)}
function count(events,type){return events.filter(e=>e.eventType===type).length}
function renderStatus(s){
  document.getElementById('statusText').textContent=s.monitoringEnabled?'ON':'PAUSED';
  document.getElementById('statusHint').textContent=s.monitoringEnabled?'Approved activity is being recorded locally.':'Monitoring is paused by a parent. No new events are recorded.';
  document.getElementById('statusDot').classList.toggle('off',!s.monitoringEnabled);
}
async function refresh(){
  const r=await send({type:'GET_STATUS'}); const all=await send({type:'GET_EVENTS',limit:500}); if(!r?.ok)return;
  const s=r.settings, ev=all?.events||r.recentEvents||[];
  renderStatus(s);
  document.getElementById('uploads').textContent=count(ev,'file_upload');
  document.getElementById('downloads').textContent=count(ev,'file_download');
  document.getElementById('searches').textContent=count(ev,'search');
  document.getElementById('visits').textContent=count(ev,'page_visit');
  document.getElementById('chats').textContent=count(ev,'chat_message');
  document.getElementById('pending').textContent=r.pendingCount;
  document.getElementById('backend').textContent=s.backendEnabled?(s.backendBaseUrl?'Configured':'Enabled, no URL'):'Not connected';
}
document.getElementById('settings').onclick=()=>chrome.runtime.openOptionsPage();
document.getElementById('activity').onclick=()=>chrome.tabs.create({url:chrome.runtime.getURL('src/dashboard/dashboard.html')});
document.getElementById('sync').onclick=async()=>{const b=document.getElementById('backend');b.textContent='Syncing…';const r=await send({type:'SYNC_NOW'});b.textContent=r?.result?.success?'Synced':'Not connected';refresh()};
// Ask the service worker to re-check the backend's real monitoring
// status every time the popup is opened, so a parent's toggle from the
// dashboard shows up here immediately instead of waiting for the next
// periodic poll (up to 5 min away — see service-worker.js).
(async()=>{await send({type:'CHECK_MONITORING_STATUS'}); refresh();})();
