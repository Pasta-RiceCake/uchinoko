/* ===== 保存とふたりの共有（本番） ===== */
// このスマホだけの設定。共有しない
const PRIV=new Set(["th","col","icm","me","home","share","app","seedCh","setup"]);
const shK=()=>Object.keys(S).filter(k=>!PRIV.has(k)&&k[0]!=="_");
const outV=k=>k==="plans"?S.plans.filter(p=>p.vis!=="自分だけ"):S[k];
const hs=t=>{let h=0;for(let i=0;i<t.length;i++)h=(h*31+t.charCodeAt(i))|0;return h};
S._sync=S._sync||{rev:0,h:{}};
const persist=()=>{try{localStorage.setItem(KEY,JSON.stringify(S))}catch(e){}};
let syT=null,syBusy=false,syAgain=false,pendR=false,shOffArm=false;
const save=()=>{persist();if(S.share.on){clearTimeout(syT);syT=setTimeout(syncNow,1200)}};
function dirty(){const o={};for(const k of shK()){const j=JSON.stringify(outV(k)??null);if(S._sync.h[k]!==hs(j))o[k]=JSON.parse(j)}return o}
function applyUpd(u){for(const k in u){if(PRIV.has(k)||k[0]==="_")continue;
  if(k==="plans")S.plans=(u.plans||[]).concat(S.plans.filter(p=>p.vis==="自分だけ"));else S[k]=u[k];
  S._sync.h[k]=hs(JSON.stringify(outV(k)??null))}}
const api=(p,b)=>fetch(p,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(b)});
async function syncNow(){
  if(!S.share.on||!S.share.id)return;if(syBusy){syAgain=true;return}syBusy=true;
  try{const put=dirty(),r=await api("/api/fam/"+S.share.id+"/sync",{code:S.share.code,rev:S._sync.rev,put});
    if(!r.ok)return;const j=await r.json();
    for(const k in put)S._sync.h[k]=hs(JSON.stringify(put[k]));
    const n=Object.keys(j.upd||{}).length;applyUpd(j.upd||{});S._sync.rev=j.rev;persist();if(n)softRender();
  }catch(e){}finally{syBusy=false;if(syAgain){syAgain=false;syncNow()}}
}
// 入力中に画面を書きかえない
const typing=()=>/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName||"");
function softRender(){if(typing()){pendR=true;return}render(true)}
document.addEventListener("focusout",()=>{if(pendR)setTimeout(()=>{if(pendR&&!typing()){pendR=false;render(true)}},80)});
setInterval(()=>{if(!document.hidden)syncNow()},15000);
document.addEventListener("visibilitychange",()=>{if(!document.hidden)syncNow()});
window.addEventListener("online",()=>syncNow());
async function shStart(){toast("リンクを作っています…");
  const put={};for(const k of shK())put[k]=outV(k)??null;
  try{const r=await api("/api/fam",{put});if(!r.ok)throw 0;const j=await r.json();
    S.share={on:true,id:j.id,code:j.code};S._sync={rev:j.rev,h:{}};for(const k in put)S._sync.h[k]=hs(JSON.stringify(put[k]));
    persist();render(true);document.querySelector(".shc")?.setAttribute("open","");toast("共有リンクを作りました");
  }catch(e){toast("つながりませんでした。電波のよい所でもう一度押してください")}}
