export const dashboardHtml = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YWP OS Marketing Bot</title>
<style>
:root{color-scheme:dark;--gold:#d7b84b;--bg:#080808;--panel:#151515;--muted:#9c9c9c}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#2b2108 0,#080808 40%);font-family:Inter,Arial,sans-serif;color:#fff}.wrap{max-width:1100px;margin:auto;padding:28px}.top{display:flex;align-items:center;justify-content:space-between;gap:20px}.brand{font-size:28px;font-weight:900;letter-spacing:2px;color:var(--gold)}button{background:var(--gold);color:#060606;border:0;border-radius:10px;padding:11px 15px;font-weight:800;cursor:pointer}button.secondary{background:#282828;color:#fff;border:1px solid #494949}.notice{margin:22px 0;padding:14px 16px;border:1px solid #5a4915;background:#171307;border-radius:12px;color:#e7d78c}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:18px}.card{background:rgba(20,20,20,.96);border:1px solid #3d3420;border-radius:18px;overflow:hidden}.card img{width:100%;aspect-ratio:4/5;object-fit:cover;background:#000}.body{padding:16px}.status{display:inline-block;padding:5px 9px;border-radius:999px;background:#262626;color:var(--gold);font-size:12px;font-weight:900}.meta{color:var(--muted);font-size:13px;line-height:1.5}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:13px}.blocked{color:#ff8d8d}.empty{padding:60px;text-align:center;color:var(--muted);border:1px dashed #444;border-radius:16px}code{color:#e9cf70}</style></head>
<body><div class="wrap"><div class="top"><div><div class="brand">♛ YWP OS MARKETING BOT</div><div class="meta">Approval-first Instagram publishing</div></div><button onclick="syncCards()">Sync YWP OS</button></div>
<div class="notice">Nothing publishes until a draft passes YWP verification, you approve it, and Instagram publishing is enabled.</div><div id="app" class="grid"></div></div>
<script>
const key=()=>sessionStorage.ywpKey||(sessionStorage.ywpKey=prompt('Enter ADMIN_KEY')||'');
async function api(url,options={}){const r=await fetch(url,{...options,headers:{'content-type':'application/json','x-ywp-admin-key':key(),...(options.headers||{})}});const p=await r.json();if(!r.ok)throw new Error(p.error||JSON.stringify(p));return p}
function esc(s){return String(s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function draftCard(d){
  const blocked=d.blockReasons.length?'<p class="blocked">'+d.blockReasons.map(esc).join('<br>')+'</p>':'';
  const approve=d.status==='DRAFT'&&!d.blockReasons.length?'<button onclick="act(\''+d.id+'\',\'approve\')">Approve</button>':'';
  const publish=d.status==='APPROVED'?'<button onclick="act(\''+d.id+'\',\'publish\')">Publish</button>':'';
  const caption=encodeURIComponent(d.caption);
  return '<article class="card"><img src="/generated/'+esc(d.imageFilename)+'"><div class="body"><span class="status">'+esc(d.status)+'</span><h3>'+esc(d.card.title)+'</h3><div class="meta">'+esc(d.card.sport)+' • '+esc(d.card.verifiedAsOf)+'<br>'+d.card.legs.length+' pick(s)</div>'+blocked+'<div class="actions">'+approve+publish+'<button class="secondary" data-caption="'+caption+'" onclick="copyCaption(this)">Copy caption</button></div></div></article>';
}
function copyCaption(button){navigator.clipboard.writeText(decodeURIComponent(button.dataset.caption))}
async function load(){try{const p=await api('/api/drafts');const root=document.getElementById('app');root.innerHTML=p.drafts.length?p.drafts.map(draftCard).join(''):'<div class="empty">No drafts yet. Sync YWP OS after the marketing feed is connected.</div>'}catch(e){document.getElementById('app').innerHTML='<div class="empty blocked">'+esc(e.message)+'</div>'}}
async function syncCards(){try{const p=await api('/api/sync',{method:'POST'});alert('Created '+p.created+'; skipped '+p.skipped);load()}catch(e){alert(e.message)}}
async function act(id,action){try{await api('/api/drafts/'+id+'/'+action,{method:'POST'});load()}catch(e){alert(e.message)}}load();
</script></body></html>`;
