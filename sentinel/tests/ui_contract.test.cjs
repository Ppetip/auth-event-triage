/* DOM-contract tests, not a substitute for a real browser E2E test. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor(tag='div') { this.tag=tag; this.children=[]; this.textContent=''; this.value=''; this.listeners={}; this.attrs={}; }
  appendChild(x) { this.children.push(x); return x; }
  replaceChildren(...xs) { this.children=xs; }
  addEventListener(name, fn) { this.listeners[name]=fn; }
  setAttribute(k,v) { this.attrs[k]=v; }
  async click() { await this.listeners.click(); await new Promise(resolve=>setTimeout(resolve,5)); }
}
const ids=['status','token','connect','refresh','filter','host','events-total','alerts-total','open-total','hosts-total','alerts-body','events-body'];
const els=Object.fromEntries(ids.map(id=>[id,new Element()]));
const calls=[];
let acked=false;
const data={id:1,host:'node-1',kind:'host_down',message:'Host unavailable',timestamp:'2026-10-24T00:00:00Z',acknowledged:0};
const fetch=async (url, options) => {
  calls.push([url,options]);
  if(url==='/api/stats') return {ok:true,json:async()=>({events:1,alerts:1,unacknowledged:acked?0:1,hosts:1})};
  if(url==='/api/alerts') return {ok:true,json:async()=>({alerts:[{...data,acknowledged:acked?1:0}]})};
  if(url.startsWith('/api/events')) return {ok:true,json:async()=>({events:url.includes('host=missing')?[]:[{host:'node-1',kind:'host_down',detail:'<script>attack()</script>',timestamp:data.timestamp}]})};
  if(url==='/api/alerts/1/ack') {acked=true;return {ok:true,json:async()=>({acknowledged:true})};}
  return {ok:false,status:404};
};
const document={getElementById:id=>els[id],createElement:tag=>new Element(tag)};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8'),{document,fetch,console});
(async()=>{
  els.token.value='reader_secret';
  await els.connect.click();
  assert.equal(els.token.value,'','token must be cleared from input');
  assert.equal(els['alerts-total'].textContent,1);
  assert.equal(els['events-body'].children[0].children[3].textContent,'<script>attack()</script>','untrusted detail rendered as text');
  assert.equal(els['alerts-body'].children[0].children[5].children[0].attrs['aria-label'],'Acknowledge alert 1 on node-1');
  await els['alerts-body'].children[0].children[5].children[0].click();
  assert.equal(els['open-total'].textContent,0);
  els.host.value='missing'; await els.filter.click();
  assert.equal(els['events-body'].children[0].children[0].textContent,'No events');
  await els.refresh.click();
  assert.ok(calls.every(([,opts])=>opts.headers.Authorization==='Bearer reader_secret'));
  assert.equal(els.status.textContent,'Updated successfully.');
  console.log('PASS UI DOM contracts: connect, token handling, alert acknowledgement, filter, refresh, safe text rendering');
})().catch(e=>{console.error(e);process.exitCode=1;});
