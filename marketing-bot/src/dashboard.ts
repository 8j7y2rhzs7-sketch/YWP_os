export const dashboardHtml = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YWP OS Marketing Bot</title>
<style>
:root{color-scheme:dark;--gold:#d7b84b;--bg:#080808;--panel:#151515;--muted:#9c9c9c}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#2b2108 0,#080808 40%);font-family:Georgia,"Times New Roman",serif;color:#fff}.wrap{max-width:1100px;margin:auto;padding:28px}.top{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap}.brand{font-size:28px;font-weight:900;letter-spacing:2px;color:var(--gold)}.actions-top{display:flex;gap:10px;flex-wrap:wrap}button{background:var(--gold);color:#060606;border:0;border-radius:10px;padding:11px 15px;font-weight:800;cursor:pointer;font-family:inherit}button.secondary{background:#282828;color:#fff;border:1px solid #494949}.notice{margin:22px 0;padding:14px 16px;border:1px solid #5a4915;background:#171307;border-radius:12px;color:#e7d78c;line-height:1.45}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:18px}.card{background:rgba(20,20,20,.96);border:1px solid #3d3420;border-radius:18px;overflow:hidden}.card img{width:100%;aspect-ratio:4/5;object-fit:cover;background:#000}.body{padding:16px}.status{display:inline-block;padding:5px 9px;border-radius:999px;background:#262626;color:var(--gold);font-size:12px;font-weight:900}.meta{color:var(--muted);font-size:13px;line-height:1.5;font-family:Arial,sans-serif}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:13px}.blocked{color:#ff8d8d}.empty{padding:60px;text-align:center;color:var(--muted);border:1px dashed #444;border-radius:16px;font-family:Arial,sans-serif}code{color:#e9cf70}h3{margin:10px 0 6px}
</style></head>
<body><div class="wrap">
<div class="top">
  <div><div class="brand">♛ YWP OS MARKETING</div><div class="meta">Brand creatives — not live tickets</div></div>
  <div class="actions-top">
    <button onclick="makePromo()">Make promo post</button>
    <button class="secondary" onclick="syncCards()">Sync feed (optional)</button>
  </div>
</div>
<div class="notice">Default path: <b>Make promo post</b> → <b>Download image</b> → <b>Copy caption</b> → paste into Instagram. Promo posts are marketing process/brand content, not real picks. Auto-publish to Meta is optional and off by default.</div>
<div id="app" class="grid"></div></div>
<script>
const key=()=>sessionStorage.ywpKey||(sessionStorage.ywpKey=prompt('Enter ADMIN_KEY')||'');
async function api(url,options={}){const r=await fetch(url,{...options,headers:{'content-type':'application/json','x-ywp-admin-key':key(),...(options.headers||{})}});const p=await r.json();if(!r.ok)throw new Error(p.error||JSON.stringify(p));return p}
function esc(s){return String(s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function draftCard(d){
  const blocked=d.blockReasons.length?'<p class="blocked">'+d.blockReasons.map(esc).join('<br>')+'</p>':'';
  const promo=d.card.sourceVersion==='promo'||String(d.card.id).startsWith('promo-');
  const approve=!promo&&d.status==='DRAFT'&&!d.blockReasons.length?'<button onclick="act(\\''+d.id+'\\',\\'approve\\')">Approve</button>':'';
  const publish=!promo&&d.status==='APPROVED'?'<button onclick="act(\\''+d.id+'\\',\\'publish\\')">Publish</button>':'';
  const caption=encodeURIComponent(d.caption);
  const img='/generated/'+esc(d.imageFilename);
  return '<article class="card"><img src="'+img+'"><div class="body"><span class="status">'+(promo?'PROMO':esc(d.status))+'</span><h3>'+esc(d.card.title)+'</h3><div class="meta">'+esc(d.card.sport)+(promo?' • marketing creative':'')+'</div>'+blocked+'<div class="actions"><a href="'+img+'" download="ywp-'+esc(d.card.title).replace(/\\s+/g,'-')+'.png"><button type="button">Download image</button></a><button class="secondary" data-caption="'+caption+'" onclick="copyCaption(this)">Copy caption</button>'+approve+publish+'</div></div></article>';
}
function copyCaption(button){navigator.clipboard.writeText(decodeURIComponent(button.dataset.caption));button.textContent='Copied';setTimeout(()=>button.textContent='Copy caption',1200)}
async function load(){try{const p=await api('/api/drafts');const root=document.getElementById('app');root.innerHTML=p.drafts.length?p.drafts.map(draftCard).join(''):'<div class="empty">No creatives yet. Hit <b>Make promo post</b> — one click, then download + copy caption into Instagram.</div>'}catch(e){document.getElementById('app').innerHTML='<div class="empty blocked">'+esc(e.message)+'</div>'}}
async function makePromo(){try{const kind=prompt('Optional theme: process | brand | sport_night | responsible (or leave blank)','')||undefined;const sport=prompt('Optional sport label (MLB, NFL, WNBA…) or blank','')||undefined;await api('/api/promo',{method:'POST',body:JSON.stringify({kind,sport})});load()}catch(e){alert(e.message)}}
async function syncCards(){try{const p=await api('/api/sync',{method:'POST'});alert('Feed sync: created '+p.created+', skipped '+p.skipped);load()}catch(e){alert(e.message)}}
async function act(id,action){try{await api('/api/drafts/'+id+'/'+action,{method:'POST'});load()}catch(e){alert(e.message)}}
load();
</script></body></html>`;
