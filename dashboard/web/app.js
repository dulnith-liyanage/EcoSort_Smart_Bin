'use strict';
const $ = id => document.getElementById(id);
const labels = {paper:'Paper & cardboard',plastic:'Rigid plastic',metal:'Metal cans',food:'Fruit & veg scraps'};
const colors = {paper:'#86b7ff',plastic:'#f2b16d',metal:'#87cba5',food:'#f0948c'};
const positions = {paper:'Front-left',plastic:'Front-right',metal:'Rear-left',food:'Rear-right'};
const symbols = {
  paper:'<path d="M6 3h9l4 4v14H6V3Zm9 0v5h4M9 12h7m-7 4h5"/>',
  plastic:'<path d="M10 3h4v5l3 4v8H7v-8l3-4V3Zm0 3h4M7 14h10"/>',
  metal:'<ellipse cx="12" cy="5" rx="6" ry="2"/><path d="M6 5v14c0 3 12 3 12 0V5M9 11v5"/>',
  food:'<path d="M12 7c-9-5-12 9-5 13 2 1 3 0 5 0s3 1 5 0c7-4 4-18-5-13Zm0 0c0-5 3-5 5-5 0 4-2 5-5 5Z"/>'
};
const phases = {idle:'Not running',loading:'Starting up',calibrating:'Preparing the tray',ready:'Sorting is on',waiting_clear:'Waiting for an empty tray',observing:'Sorting paused',sorting:'Sorting this item',cooldown:'Returning to ready',stopping:'Finishing the current cycle',error:'Needs attention'};
let latest, connected=false, pending=false, frameLoading=false, frameAt=null, historyKey='', toastTimer;
const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const score = value => Number.isFinite(value) ? `${Math.round(value*100)}%` : '—';
function toast(message) { $('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{$('toast').hidden=true;},5000); }
async function api(path,body) {
  const response=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json','X-EcoSort-Request':'1'},body:JSON.stringify(body)}:{});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||'Request failed.');
  return data;
}
function details(entries) { $('device-info').innerHTML=entries.map(([name,value])=>`<dt>${esc(name)}</dt><dd>${esc(value)}</dd>`).join(''); }
function camera(data) {
  const s=data.state, fresh=s.frame_at && Date.now()/1000-s.frame_at<8 && !['idle','error'].includes(s.phase);
  $('camera-status').textContent=data.demo?'Sample view':fresh?'Live':s.frame_at?'Stream delayed':'Standby';
  $('frame-note').hidden=fresh||!s.frame_at;
  $('placeholder-title').textContent=data.demo?'No camera in demo mode.':s.phase==='loading'?'Preparing the camera…':'Ready when the Pi is.';
  $('placeholder-text').textContent=data.demo?'Try a sample item to explore the simpler dashboard.':'The camera will appear here when sorting starts.';
  if(!fresh){const showLast=frameAt&&s.frame_at&&!['idle','error'].includes(s.phase);$('frame').hidden=!showLast;$('placeholder').hidden=Boolean(showLast);return;}
  if(frameLoading||frameAt===s.frame_at)return;
  frameLoading=true;
  $('frame').onload=()=>{frameLoading=false;frameAt=s.frame_at;$('frame').hidden=false;$('placeholder').hidden=true;};
  $('frame').onerror=()=>{frameLoading=false;};
  $('frame').src=`/api/frame.jpg?t=${s.frame_at}`;
}
function render(data) {
  latest=data;
  const s=data.state, active=!['idle','error'].includes(s.phase), starting=['loading','calibrating'].includes(s.phase);
  $('connection').textContent='Connected';$('connection').className='connection online';
  $('mode').hidden=!data.demo&&data.mode==='hardware';
  $('mode').textContent=data.demo?'Demo · no hardware':'Observation · no motors';
  $('category').textContent=labels[s.category]||'Waiting for an item';
  $('prediction').textContent=s.category?`${positions[s.category]} · ${score(s.score)} match score`:'One item at a time, in the centre of the tray.';
  $('material-icon').innerHTML=s.category&&symbols[s.category]?`<svg viewBox="0 0 24 24">${symbols[s.category]}</svg>`:'—';
  $('material-icon').style.color=colors[s.category]||'#a4c6aa';
  $('status-label').textContent=phases[s.phase]||s.phase;
  $('message').textContent=s.phase==='calibrating'?(s.auto_sort?'Keep the tray empty for a moment. Sorting starts after calibration.':'Keep the tray empty for a moment. Sorting will remain paused.'):s.phase==='loading'?'The website is ready. The camera and model are starting.':s.phase==='observing'?'The camera and classifier are still running.':s.phase==='sorting'?'Moving the tray towards the selected bin.':s.phase==='cooldown'?'Route completed. Waiting for the tray to clear.':s.phase==='waiting_clear'?'Previous route finished. Remove any remaining item and keep the tray clear briefly.':s.phase==='ready'&&!data.demo?(s.message.includes('low confidence')?'Reposition the item for a clearer view.':s.category?'Checking the item…':'Place one item on the tray.'):s.message;
  $('control').textContent=starting?'Pause after startup':s.phase==='stopping'?'Finishing…':!active?'Start sorting':s.paused?'Resume sorting':'Pause sorting';
  $('control').disabled=pending||!connected||s.phase==='stopping'||(starting&&s.paused);
  $('control-note').textContent=starting?'Loading the model and learning the empty tray.':data.demo?'Sample data only. No physical movement.':s.phase==='error'?'Check the assembly before starting again.':active?(s.paused?'The camera and classifier stay on while paused.':'Pause stops the next route; the current cycle finishes first.'):'A physical session commands HOME before sorting.';
  // Pausing is also allowed during startup to cancel automatic motor routing.
  if(starting&&!pending&&connected){$('control').textContent=s.auto_sort?'Pause sorting':'Starting · sorting paused';$('control').disabled=!s.auto_sort;}
  $('reset').hidden=!(active&&s.paused&&!starting&&!['sorting','cooldown','stopping'].includes(s.phase));
  $('reset').disabled=pending||!connected;
  $('sample').hidden=!data.demo||!active;$('sample').disabled=pending||!connected;
  $('bins').innerHTML=Object.entries(labels).map(([key,name])=>`<article class="bin${s.category===key?' selected':''}" data-category="${key}"><h3>${name}</h3><strong>${data.counts[key]}</strong></article>`).join('');
  document.querySelectorAll('.bin').forEach(el=>el.style.setProperty('--color',colors[el.dataset.category]));
  const signature=data.events.slice(0,5).map(e=>e.id).join(',');
  if(signature!==historyKey||!$('events').childNodes.length){
    historyKey=signature;
    $('events').innerHTML=data.events.length?data.events.slice(0,5).map(e=>`<div class="event"><strong>${esc(labels[e.category])}</strong><span>${esc(new Date(e.at*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}))} · ${e.mode==='hardware'?'Command completed':'Simulated'}</span></div>`).join(''):'<p>No completed routes yet.</p>';
  }
  const h=data.health,c=data.calibration;
  details([['Device',data.hostname],['Temperature',h.temperature===null?'Unavailable':`${h.temperature} °C`],['Memory used',h.memory_percent===null?'Unavailable':`${h.memory_percent}%`],['HOME',c.error||`Pan ${c.pan_home}° / Tilt ${c.tilt_home}°`],['Model',s.model==='siglip2'?'SigLIP 2':'CLIP'],['Inference time',s.inference_ms===null?'—':`${s.inference_ms} ms`],['Power flags',h.throttled?.raw??'Unavailable'],...data.categories.map(r=>[r.name,`Pan ${r.pan??'—'}° / Tilt ${r.tilt??'—'}°`])]);
  const power=h.throttled;
  $('notice').hidden=!(data.demo||power?.undervoltage_now||power?.undervoltage_recorded||s.phase==='error');
  $('notice').textContent=s.phase==='error'?s.message:power?.undervoltage_now?'Low voltage detected. Pause sorting and check the Pi power supply.':power?.undervoltage_recorded?'A low-voltage event was recorded during this boot. Check the Pi supply before extended use.':data.demo?'Design preview. Sample items only; no camera or motors are connected.':'';
  $('updated').textContent=`Updated ${new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}`;
  camera(data);
}
async function refresh() {
  try{const data=await api('/api/state');connected=true;render(data);}
  catch(error){connected=false;$('connection').textContent='Disconnected';$('connection').className='connection offline';$('notice').hidden=false;$('notice').textContent='Connection lost. Reconnecting automatically…';['control','reset','sample'].forEach(id=>{$(id).disabled=true;});$('camera-status').textContent='Offline';$('frame-note').hidden=$('frame').hidden;$('frame-note').textContent='Disconnected · last frame';}
}
async function command(action){
  if(pending||!connected)return;
  pending=true;$('control').disabled=true;
  try{await api('/api/command',{action});await refresh();}
  catch(error){toast(error.message);}
  finally{pending=false;if(latest&&connected)render(latest);}
}
$('control').addEventListener('click',()=>{
  if(!latest)return;
  const phase=latest.state.phase;
  if(['idle','error'].includes(phase)){
    if(latest.hardware_allowed&&!confirm('Starting commands HOME and enables sorting after the empty-tray calibration. Is the tray empty and the mechanism clear?'))return;
    command('start');
  }else command(['loading','calibrating'].includes(phase)?'pause':latest.state.paused?'resume':'pause');
});
$('reset').addEventListener('click',()=>{if(confirm('Remove all items and hands from the tray, then reset its empty reference?'))command('recalibrate');});
$('sample').addEventListener('click',()=>command('scan'));
async function poll(){await refresh();setTimeout(poll,1500);}
poll();
