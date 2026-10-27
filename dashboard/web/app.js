'use strict';
const $ = (id) => document.getElementById(id);
const icons = {paper:'paper', plastic:'bottle', metal:'can', food:'food'};
const names = {paper:'Paper & cardboard', plastic:'Rigid plastic', metal:'Metal cans', food:'Fruit & veg scraps'};
const positions = {paper:'Front-left', plastic:'Front-right', metal:'Rear-left', food:'Rear-right'};
const phases = {idle:'Ready when you are', loading:'Loading model', calibrating:'Learning the empty tray', observing:'Observing the tray', ready:'Routing enabled', sorting:'Route in progress', cooldown:'Returning to observation', stopping:'Finishing this session', error:'Session needs attention'};
let latest = null, connected = false, pending = false, view = 'overview', dialogAction = null, guides = true;
let frameLoading = false, renderedFrameAt = null, toastTimer, activitySignature = '';
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon = (name) => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const pct = (value) => Number.isFinite(value) ? `${Math.round(value * 100)}%` : '—';
const timeLabel = (at) => new Date(at*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});
const duration = (seconds) => Number.isFinite(seconds) ? `${Math.floor(seconds/3600)}h ${Math.floor(seconds%3600/60)}m` : 'Unavailable';
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => {$('toast').hidden = true;}, 5000); }
async function api(path, body) {
  const response = await fetch(path, body ? {method:'POST',headers:{'Content-Type':'application/json','X-EcoSort-Request':'1'},body:JSON.stringify(body)} : {});
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && path !== '/api/login' && !$('login-dialog').open) $('login-dialog').showModal();
    throw new Error(data.error || 'Request failed.');
  }
  return data;
}
function setView(name) {
  view = name;
  const titles = {overview:['LIVE OPERATIONS','A clearer view of every sort.','Watch the tray, understand the decision, follow the route.'], activity:['LOCAL EVENT HISTORY','The story behind every route.','Inspect completed commands and export your demonstration log.'], system:['DEVICE & CALIBRATION','Know what is happening underneath.','Real device readings and saved calibration, in one place.']};
  if (!titles[name]) return;
  for (const section of ['overview','activity','system']) $(`${section}-view`).hidden = section !== name;
  document.querySelectorAll('.nav').forEach(b => {b.classList.toggle('active',b.dataset.view===name); if(b.dataset.view===name)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
  [$('page-eyebrow').textContent,$('page-title').textContent,$('page-description').textContent] = titles[name];
  $('breadcrumb').textContent = {overview:'Overview', activity:'Activity log', system:'System & calibration'}[name];
  if (name === 'overview' && latest) refreshFrame(latest);
}
document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click',()=>setView(b.dataset.view)));
function table(events, recent=false) {
  if (!events.length) return `<div class="empty-state">${icon('clock')}<strong>No route cycles yet</strong>Completed commands will appear here. Predictions alone do not add to the count.</div>`;
  return `<div class="table-wrap"><table><thead><tr><th>Material</th><th>Time</th><th>Match score</th><th>Destination</th><th>Outcome</th></tr></thead><tbody>${events.map(e => `<tr><td><span class="table-material ${esc(e.category)}">${icon(icons[e.category] || 'paper')}${esc(names[e.category] || e.category)}</span></td><td>${esc(timeLabel(e.at))}${recent?'':`<br><span class="mode-tag">${esc(new Date(e.at*1000).toLocaleDateString())}</span>`}</td><td><span class="table-score"><i><b data-width="${Number(e.score)*100}"></b></i>${pct(e.score)}</span></td><td>${esc(positions[e.category])}</td><td><span class="outcome">${e.mode==='hardware'?'Command completed':'Simulated cycle'}</span><br><span class="mode-tag">${e.mode==='demo'?'DEMO':e.mode==='observe'?'NO MOTOR OUTPUT':'DELIVERY UNVERIFIED'}</span></td></tr>`).join('')}</tbody></table></div>`;
}
function renderActivity(data) {
  const category = $('filter').value, mode = $('mode-filter').value;
  const signature = `${category}:${mode}:${data.events.map(e=>e.id).join(',')}`;
  if (signature === activitySignature) return;
  activitySignature = signature;
  $('recent-events').innerHTML = table(data.events.slice(0,4), true);
  $('all-events').innerHTML = table(data.events.filter(e => (category==='all'||e.category===category) && (mode==='all'||e.mode===mode)));
  document.querySelectorAll('[data-width]').forEach(el=>{el.style.width=`${Math.max(0,Math.min(100,Number(el.dataset.width)||0))}%`;});
}
$('filter').addEventListener('change',()=>{if(latest)renderActivity(latest);});
$('mode-filter').addEventListener('change',()=>{if(latest)renderActivity(latest);});
function details(id, entries) { $(id).innerHTML = entries.map(([key,value]) => `<div class="detail-row"><span>${esc(key)}</span><strong>${esc(value)}</strong></div>`).join(''); }
function render(data) {
  latest = data;
  const s = data.state, active = !['idle','error'].includes(s.phase), busy = ['loading','stopping'].includes(s.phase);
  const score = s.category ? s.score : null;
  $('demo-banner').hidden = !data.demo;
  $('connection').textContent = data.demo ? 'Demo connected' : 'Device connected';
  $('connection').className = 'badge';
  $('sidebar-host').textContent = data.demo ? 'Design preview' : data.hostname;
  $('side-dot').style.background = '#a6cba0';
  $('total').textContent = Object.values(data.counts).reduce((a,b)=>a+b,0);
  $('count-note').textContent = data.mode === 'hardware' ? 'Physical commands · delivery unverified' : data.demo ? 'Sample cycles · demonstration data' : 'Simulated commands · no motor output';
  $('metric-score').textContent = pct(score);
  $('latency').innerHTML = Number.isFinite(s.inference_ms) ? `${Math.round(s.inference_ms)}<small>ms</small>` : '—';
  $('temperature').innerHTML = Number.isFinite(data.health.temperature) ? `${data.health.temperature.toFixed(1)}<small>°C</small>` : '—';
  $('temp-note').textContent = data.health.temperature===null ? 'Not available on this host' : 'Device temperature · read every 10 seconds';
  $('phase-label').textContent = phases[s.phase] || s.phase;
  $('mode-label').textContent = data.demo ? 'Design preview · no hardware' : data.mode === 'hardware' && active ? 'Physical motors · PCA9685' : active ? 'Observation · motors inactive' : 'Motors inactive';
  $('start-session').hidden = active;
  $('stop-session').hidden = !active;
  $('pause-resume').hidden = !active;
  $('pause-resume').disabled = busy || pending || !connected;
  $('pause-resume').innerHTML = `${icon(s.paused?'play':'pause')}<span>${s.paused?'Enable routing':'Pause routing'}</span>`;
  $('start-session').disabled = pending || !connected;
  $('stop-session').disabled = pending || s.phase==='stopping' || !connected;
  $('scan').disabled = !active || busy || pending || s.phase==='calibrating' || !connected;
  $('scan').querySelector('span').textContent = data.demo ? 'Run sample' : 'Scan tray';
  $('recalibrate').disabled = !active || busy || pending || !s.paused || s.phase==='sorting' || s.phase==='cooldown' || !connected;
  $('snapshot').disabled = !s.frame_at || !connected;
  $('prediction-title').textContent = names[s.category] || 'Waiting for an item';
  $('prediction-sub').textContent = s.category ? `${positions[s.category]} route · ${pct(score)} relative match` : 'One item at a time, centred on the tray.';
  $('score-bars').innerHTML = Object.keys(names).map(key => `<div class="score-row ${key}"><span><i class="material-dot"></i>${names[key]}</span><span>${pct(s.scores[key])}</span><div class="bar"><span data-width="${(s.scores[key]||0)*100}"></span></div></div>`).join('');
  $('score-bars').querySelectorAll('[data-width]').forEach(el=>{el.style.width=`${Math.max(0,Math.min(100,Number(el.dataset.width)||0))}%`;});
  $('unsupported-score').textContent = `Unsupported / background match: ${pct(s.scores.unknown)}`;
  $('stability').textContent = `${s.stable || 0} / 3 stable`;
  $('gate-title').textContent = s.paused ? 'Observation only' : s.phase==='sorting' ? 'Executing route' : s.phase==='cooldown' ? 'Between cycles' : 'Decision checks active';
  $('gate-dot').classList.toggle('active',!s.paused);
  $('decision-message').textContent = s.message;
  $('bin-grid').innerHTML = data.categories.map(c => `<article class="bin-card ${c.key}${s.category===c.key?' selected':''}"><div class="bin-top"><span class="material-icon">${icon(icons[c.key])}</span><span class="bin-position">${esc(c.position)}</span></div><h3>${esc(c.name)}</h3><div class="bin-count">${data.counts[c.key]}<small>cycles today</small></div><div class="bin-route"><span>Pan ${c.pan??'—'}° · Tilt ${c.tilt??'—'}°</span>${icon('arrow')}</div></article>`).join('');
  renderActivity(data);
  const h=data.health, unavailable='Unavailable';
  details('health-readings',[
    ['Device',data.hostname],['Temperature',h.temperature===null?unavailable:`${h.temperature} °C`],
    ['Memory used',h.memory_percent===null?unavailable:`${h.memory_percent}%`],
    ['1-minute load average',h.load??unavailable],['Device uptime',duration(h.uptime)],
    ['Disk used',h.disk_percent===null?unavailable:`${h.disk_percent}%`],
    ['Firmware power flags',h.throttled?.raw??unavailable],
    ['Undervoltage now',h.throttled ? (h.throttled.undervoltage_now?'Detected':'Not flagged') : unavailable],
    ['Undervoltage this boot',h.throttled ? (h.throttled.undervoltage_recorded?'Recorded':'Not flagged') : unavailable]
  ]);
  const c=data.calibration;
  details('calibration',c.error ? [['Calibration error',c.error]] : [
    ['HOME',`Pan ${c.pan_home}° / Tilt ${c.tilt_home}°`],
    ...data.categories.map(r=>[`${r.name} · ${r.position}`,`Pan ${r.pan}° / Tilt ${r.tilt}°`]),
    ['Movement',`1° steps / ${Math.round(c.step_delay*1000)} ms`],['Shake',`${c.shake_degrees}°`],
    ['Automatic score / margin','60% / 15 percentage points'],['Stability / cooldown','3 predictions / 3.8 seconds']
  ]);
  const power=h.throttled;
  $('power-banner').hidden = !(power && (power.undervoltage_now || power.undervoltage_recorded));
  $('power-banner').textContent = power?.undervoltage_now ? 'Undervoltage is currently flagged. Pause routing and check the Pi supply and cable before further load tests.' : 'An undervoltage event was recorded during this boot. This is a historical flag; inspect the power supply before extended operation.';
  $('last-sync').textContent = `Synced ${new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'})}`;
  refreshFrame(data);
}
function refreshFrame(data) {
  const s=data.state, age=s.frame_at ? Date.now()/1000-s.frame_at : Infinity;
  const fresh=age<8 && !['idle','error'].includes(s.phase);
  $('camera-badge').textContent = data.demo?'Sample view':fresh?'Live':s.frame_at?'Last frame':'Standby';
  $('camera-badge').className = `badge${fresh?'':' neutral'}`;
  $('feed-label').textContent = data.demo?'DESIGN PREVIEW · NO CAMERA':fresh?'CAMERA V2 · LIVE':'CAMERA V2 · STANDBY';
  $('frame-status').textContent = data.demo?'Illustration · not a live camera':fresh?`${Math.round(s.fps)} capture FPS · preview capped at 2 FPS`:s.frame_at?'Last frame · stream is stale':'No camera session';
  $('camera-placeholder-title').textContent = data.demo?'A better destination, by design.':s.phase==='loading'?'Preparing the camera & model…':'Your next sort starts here.';
  $('camera-placeholder-description').textContent = data.demo?'Start a sample session to explore the workflow. No hardware is used.':'Start a camera session to see the live tray.';
  if (!fresh) {
    $('camera-frame').hidden=true; $('camera-placeholder').hidden=false;
  } else if (view==='overview' && !frameLoading && renderedFrameAt!==s.frame_at) {
    frameLoading=true;
    const frame=$('camera-frame');
    frame.onload=()=>{frameLoading=false;renderedFrameAt=s.frame_at;frame.hidden=false;$('camera-placeholder').hidden=true;};
    frame.onerror=()=>{frameLoading=false;frame.hidden=true;$('camera-placeholder').hidden=false;};
    frame.src=`/api/frame.jpg?t=${s.frame_at}`;
  }
}
async function refresh() {
  try {
    const data=await api('/api/state'); connected=true; $('offline-banner').hidden=true; render(data);
  } catch(error) {
    connected=false; $('connection').textContent='Disconnected';$('connection').className='badge red';
    $('side-dot').style.background='#ce987b'; $('offline-banner').hidden=!latest;
    ['start-session','stop-session','pause-resume','scan','recalibrate','snapshot'].forEach(id=>{$(id).disabled=true;});
    if (latest) {$('frame-status').textContent='Connection lost · camera view is stale';$('camera-badge').textContent='Offline';}
  }
}
async function command(action, mode) {
  if(pending)return;
  pending=true;
  try {await api('/api/command',{action,mode}); await refresh();}
  finally {pending=false;if(latest&&connected)render(latest);}
}
function openAction(action) {
  if(!latest || !connected)return;
  dialogAction=action;$('action-error').textContent='';$('confirm-check').checked=false;
  $('mode-options').hidden=action!=='start' || latest.demo;
  $('hardware-option').hidden=!latest.hardware_allowed;
  document.querySelector('input[name="session-mode"][value="observe"]').checked=true;
  const descriptions={
    start:['Start a camera session','The dashboard will use the existing camera and CLIP pipeline. Close the VNC camera preview and any separate sorter first. Keep the tray empty for the first 30 frames.'],
    resume:['Enable routing?',latest.mode==='hardware'?'Accepted predictions will move the pan–tilt tray. Stay with the assembly during operation. Pausing waits for any current cycle to finish.':'This session simulates sorting decisions. It will not send motor commands.'],
    recalibrate:['Reset the empty-tray reference?','Remove all items and hands from the tray. The next 30 camera frames will establish a new background reference. Servo calibration is unchanged.'],
    stop:['End this session?','The current route, if any, finishes first. The hardware controller returns to HOME during shutdown and releases the camera. This is not an emergency power cutoff.']
  };
  const description=descriptions[action];
  $('dialog-title').textContent=latest.demo && action==='start'?'Explore a sample session':description[0];
  $('dialog-description').textContent=latest.demo && action==='start'?'No camera, model or motor hardware is used. Run sample generates labelled demonstration data.':description[1];
  updateActionOptions();$('action-dialog').showModal();
}
function updateActionOptions() {
  const hardwareStart=dialogAction==='start' && document.querySelector('input[name="session-mode"]:checked').value==='hardware' && latest.hardware_allowed;
  const needsCheck=hardwareStart || (dialogAction==='resume' && latest.mode==='hardware');
  $('confirm-label').hidden=!needsCheck;
  $('confirm-check').required=needsCheck;
  $('confirm-action').textContent = dialogAction==='start' ? latest.demo?'Start demo':hardwareStart?'Start physical session':'Start observation' : {resume:'Enable routing',recalibrate:'Reset reference',stop:'End session'}[dialogAction];
}
document.querySelectorAll('input[name="session-mode"]').forEach(el=>el.addEventListener('change',updateActionOptions));
$('start-session').addEventListener('click',()=>openAction('start'));
$('stop-session').addEventListener('click',()=>openAction('stop'));
$('pause-resume').addEventListener('click',async()=>{if(latest.state.paused)openAction('resume');else try{await command('pause');toast('Pause requested. Any active route finishes first.');}catch(e){toast(e.message);}});
$('scan').addEventListener('click',async()=>{try{await command('scan');toast(latest.demo?'Sample evaluated.':'Scan requested. Decision checks remain active.');}catch(e){toast(e.message);}});
$('recalibrate').addEventListener('click',()=>openAction('recalibrate'));
$('cancel-dialog').addEventListener('click',()=>$('action-dialog').close());
$('action-form').addEventListener('submit',async event=>{
  event.preventDefault(); if(pending)return;
  $('confirm-action').disabled=true;
  try {await command(dialogAction,dialogAction==='start'?document.querySelector('input[name="session-mode"]:checked').value:null);$('action-dialog').close();toast('Request sent. Watch session status for completion.');}
  catch(error){$('action-error').textContent=error.message;}
  finally{$('confirm-action').disabled=false;}
});
$('login-dialog').addEventListener('cancel',event=>event.preventDefault());
$('login-form').addEventListener('submit',async event=>{
  event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;
  try {await api('/api/login',{code:$('access-code').value});$('access-code').value='';$('login-error').textContent='';$('login-dialog').close();await refresh();}
  catch(error){$('login-error').textContent=error.message;}
  finally{button.disabled=false;}
});
$('overlay-toggle').addEventListener('click',()=>{guides=!guides;$('scan-box').hidden=!guides;$('overlay-toggle').textContent=guides?'Hide guides':'Show guides';$('overlay-toggle').setAttribute('aria-pressed',String(guides));});
$('fullscreen').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await $('camera-stage').requestFullscreen();}catch(_){toast('Full-screen view is unavailable in this browser.');}});
$('export').addEventListener('click',()=>{if(connected)window.location.assign('/api/history.csv');else toast('Connect to the dashboard before exporting.');});
$('snapshot').addEventListener('click',async()=>{try{const response=await fetch('/api/frame.jpg');if(!response.ok)throw new Error('Camera frame unavailable.');const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download=`ecosort-tray-${Date.now()}.jpg`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){toast(error.message);}});
function tick(){const now=new Date();$('clock').textContent=now.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});$('today').textContent=now.toLocaleDateString([],{day:'numeric',month:'short',year:'numeric'});}
tick();setInterval(tick,10000);
async function poll(){await refresh();setTimeout(poll,1500);}
poll();
