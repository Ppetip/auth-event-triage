'use strict';
let token = '';
const el = id => document.getElementById(id);
function status(message) { el('status').textContent = message; }
async function api(path, method='GET') {
  const response = await fetch(path, {method, headers:{Authorization:'Bearer '+token}});
  if (!response.ok) throw new Error('HTTP '+response.status);
  return response.json();
}
function cell(row, value) {
  const td = document.createElement('td'); td.textContent = String(value); row.appendChild(td); return td;
}
async function refresh() {
  if (!token) { status('Connect with a reader token first.'); return; }
  try {
    const host = el('host').value.trim();
    const [stats, alerts, events] = await Promise.all([
      api('/api/stats'), api('/api/alerts'), api('/api/events'+(host?'?host='+encodeURIComponent(host):''))
    ]);
    el('events-total').textContent = stats.events;
    el('alerts-total').textContent = stats.alerts;
    el('open-total').textContent = stats.unacknowledged;
    el('hosts-total').textContent = stats.hosts;
    const ab = el('alerts-body'); ab.replaceChildren();
    for (const alert of alerts.alerts) {
      const row = document.createElement('tr');
      [alert.timestamp,alert.host,alert.kind,alert.message,alert.acknowledged?'Acknowledged':'Open'].forEach(v=>cell(row,v));
      const action = cell(row,'');
      if (!alert.acknowledged) {
        const button = document.createElement('button'); button.textContent = 'Acknowledge';
        button.setAttribute('aria-label','Acknowledge alert '+alert.id+' on '+alert.host);
        button.addEventListener('click', async ()=>{
          try { await api('/api/alerts/'+alert.id+'/ack','POST'); await refresh(); }
          catch(err) { status('Acknowledgement failed: '+err.message); }
        }); action.appendChild(button);
      }
      ab.appendChild(row);
    }
    if (!alerts.alerts.length) { const r=document.createElement('tr');cell(r,'No alerts');ab.appendChild(r); }
    const eb = el('events-body'); eb.replaceChildren();
    for (const event of events.events) {
      const row = document.createElement('tr');
      [event.timestamp,event.host,event.kind,event.detail].forEach(v=>cell(row,v)); eb.appendChild(row);
    }
    if (!events.events.length) { const r=document.createElement('tr');cell(r,'No events');eb.appendChild(r); }
    status('Updated successfully.');
  } catch(err) { status('Unable to load data: '+err.message); }
}
el('connect').addEventListener('click', ()=>{token=el('token').value;el('token').value='';refresh();});
el('refresh').addEventListener('click', refresh);
el('filter').addEventListener('click', refresh);
