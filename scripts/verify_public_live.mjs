const base=process.argv[2];if(!base?.startsWith('https://'))throw Error('Provide the public HTTPS lab origin');
const get=async path=>{const r=await fetch(base+path);if(!r.ok)throw Error(`${path}: ${r.status}`);return r.json()};
const action=async data=>{const r=await fetch(base+'/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(!r.ok)throw Error(await r.text())};
const wait=async predicate=>{const end=Date.now()+20000;while(Date.now()<end){const s=await get('/api/status');if(predicate(s))return s;await new Promise(r=>setTimeout(r,150))}throw Error('Public physics state timed out')};
await new Promise((resolve,reject)=>{const ws=new WebSocket(base.replace('https:','wss:')+'/ws');const timer=setTimeout(()=>{ws.close();reject(Error('WebSocket timeout'))},15000);ws.onmessage=e=>{const s=JSON.parse(e.data);if(!s.positions)reject(Error('Missing physical poses'));clearTimeout(timer);ws.close();resolve()};ws.onerror=()=>{clearTimeout(timer);reject(Error('WebSocket failed'))}});
const before=await get('/api/status');
if(['running','paused'].includes(before.state)){console.log('PASS public HTTP/WebSocket; active user trial preserved.');process.exit(0)}
await action({action:'start',scenario:'hazard_control',label:'Publication verification · public HTTP / WebSocket / pause / step / save',settings:{controller:'amp',amp_yaw_gain:4,arrival_mode:'centered',navigation:'direct',speed:.4,seed:0,force_scale:1}});
await wait(s=>s.state==='running'&&s.sim_time>=.15);
await action({action:'pause'});const paused=await wait(s=>s.state==='paused');
await action({action:'step'});const stepped=await wait(s=>s.state==='paused'&&s.sim_time>paused.sim_time);
if(Math.abs(stepped.sim_time-paused.sim_time-.02)>1e-6)throw Error('Step was not 20 ms');
await action({action:'resume'});await wait(s=>s.state==='running'&&s.sim_time>stepped.sim_time+.1);
await action({action:'stop'});const finished=await wait(s=>s.state==='finished');
for(const name of ['video.mp4','figures.png','trace.npz','telemetry.jsonl','events.jsonl','manifest.json','summary.json','analysis.json','analysis.md']){const r=await fetch(`${base}/runs/${finished.run_id}/${name}`,{method:'HEAD'});if(!r.ok)throw Error(`Missing ${name}: ${r.status}`)}
console.log('PASS public physics pause/resume, exact 20 ms step, WSS, and nine saved artifacts:',finished.run_id);
await action({action:'select',scenario:'hazard_control'});await wait(s=>s.state==='ready');
