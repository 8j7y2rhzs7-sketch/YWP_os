export const dashboardHtml = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YWP OS Marketing Bot</title>
<style>
:root{color-scheme:dark;--gold:#d7b84b;--muted:#9c9c9c}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#2b2108 0,#080808 40%);font-family:Georgia,"Times New Roman",serif;color:#fff}.wrap{max-width:1100px;margin:auto;padding:28px}.top{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap}.brand{font-size:28px;font-weight:900;letter-spacing:2px;color:var(--gold)}.actions-top{display:flex;gap:10px;flex-wrap:wrap}button{background:var(--gold);color:#060606;border:0;border-radius:10px;padding:11px 15px;font-weight:800;cursor:pointer;font-family:inherit}button.secondary{background:#282828;color:#fff;border:1px solid #494949}button:disabled{opacity:.5;cursor:wait}.notice{margin:22px 0;padding:14px 16px;border:1px solid #5a4915;background:#171307;border-radius:12px;color:#e7d78c;line-height:1.45}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:18px}.card{background:rgba(20,20,20,.96);border:1px solid #3d3420;border-radius:18px;overflow:hidden}.card img{width:100%;aspect-ratio:4/5;object-fit:cover;background:#000}.body{padding:16px}.status{display:inline-block;padding:5px 9px;border-radius:999px;background:#262626;color:var(--gold);font-size:12px;font-weight:900}.meta{color:var(--muted);font-size:13px;line-height:1.5;font-family:Arial,sans-serif}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:13px}.empty{padding:60px;text-align:center;color:var(--muted);border:1px dashed #444;border-radius:16px;font-family:Arial,sans-serif}h3{margin:10px 0 6px}#pubState{font-family:Arial,sans-serif;font-size:13px;color:var(--muted);margin-top:6px}
</style></head>
<body><div class="wrap">
<div class="top">
  <div>
    <div class="brand">♛ YWP OS MARKETING</div>
    <div class="meta">One click. Bot handles the rest.</div>
    <div id="pubState">Checking publish mode…</div>
  </div>
  <div class="actions-top">
    <button id="goBtn" onclick="go()">Post promo</button>
    <button class="secondary" onclick="makeOnly()">Generate only</button>
  </div>
</div>
<div class="notice" id="notice">Promo creatives auto-pass safety (templates we control). After Meta is connected once, <b>Post promo</b> creates and publishes in one tap — no ticket checks, no re-verify every time.</div>
<div id="app" class="grid"></div></div>
<script>
const key=()=>sessionStorage.ywpKey||(sessionStorage.ywpKey=prompt('Enter ADMIN_KEY')||'');
let publishEnabled=false;
async function api(url,options={}){const r=await fetch(url,{...options,headers:{'content-type':'application/json','x-ywp-admin-key':key(),...(options.headers||{})}});const p=await r.json();if(!r.ok)throw new Error(p.error||JSON.stringify(p));return p}
function esc(s){return String(s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function draftCard(d){
  const promo=d.card.sourceVersion==='promo'||String(d.card.id).startsWith('promo-');
  const caption=encodeURIComponent(d.caption);
  const img='/generated/'+esc(d.imageFilename);
  const pub=d.status==='APPROVED'&&publishEnabled?'<button data-id="'+esc(d.id)+'" onclick="publishOne(this)">Publish now</button>':'';
  return '<article class="card"><img src="'+img+'"><div class="body"><span class="status">'+esc(d.status)+(promo?' · PROMO':'')+'</span><h3>'+esc(d.card.title)+'</h3><div class="meta">'+esc(d.card.sport)+(d.instagramMediaId?' · IG '+esc(d.instagramMediaId):'')+'</div><div class="actions"><a href="'+img+'" download="ywp-promo.png"><button type="button">Download</button></a><button class="secondary" data-caption="'+caption+'" onclick="copyCaption(this)">Copy caption</button>'+pub+'</div></div></article>';
}
function copyCaption(button){navigator.clipboard.writeText(decodeURIComponent(button.dataset.caption));button.textContent='Copied';setTimeout(()=>button.textContent='Copy caption',1200)}
async function load(){try{const p=await api('/api/drafts');publishEnabled=!!p.publishEnabled;document.getElementById('pubState').textContent=publishEnabled?'Auto-publish: ON — Post promo goes straight to Instagram.':'Auto-publish: OFF — Post promo still generates; turn IG_PUBLISH_ENABLED=true after one-time Meta setup.';document.getElementById('notice').textContent=publishEnabled?'One tap posts a brand creative to Instagram. No ticket verification. No approve step.':'Until Meta is connected once: Generate → Download + Copy caption → paste in IG. After Meta: same button auto-publishes.';const root=document.getElementById('app');root.innerHTML=p.drafts.length?p.drafts.map(draftCard).join(''):'<div class="empty">Nothing yet. Hit <b>Post promo</b>.</div>'}catch(e){document.getElementById('app').innerHTML='<div class="empty" style="color:#ff8d8d">'+esc(e.message)+'</div>'}}
async function go(){const btn=document.getElementById('goBtn');btn.disabled=true;try{const p=await api('/api/promo',{method:'POST',body:JSON.stringify({publish:publishEnabled})});if(p.published)alert('Published to Instagram'+(p.draft.instagramMediaId?': '+p.draft.instagramMediaId:''));else alert('Creative ready — download/copy, or enable IG publish for one-tap posting.');load()}catch(e){alert(e.message)}finally{btn.disabled=false}}
async function makeOnly(){try{await api('/api/promo',{method:'POST',body:JSON.stringify({publish:false})});load()}catch(e){alert(e.message)}}
async function publishOne(el){try{await api('/api/drafts/'+el.dataset.id+'/publish',{method:'POST'});load()}catch(e){alert(e.message)}}
load();
</script></body></html>`;
