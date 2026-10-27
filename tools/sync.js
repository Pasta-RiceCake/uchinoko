/* ===== 保存とふたりの共有（本番） ===== */
// このスマホだけの設定。共有しない
const PRIV=new Set(["th","col","icm","me","home","share","app","seedCh","setup","loc","bkAt"]);
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
  try{const put=dirty(),r=await api("/api/fam/"+S.share.id+"/sync",{code:S.share.code,rev:S._sync.rev,put,dev:S.app&&S.app.mid});
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
// すべての家族は、はじめから自動でサーバーに保存する（S.share）。パートナーとつないだら S.shared
const shOn=()=>!!(S.share.on&&S.shared);
async function shStart(quiet){if(!quiet)toast("リンクを作っています…");
  const put={};for(const k of shK())put[k]=outV(k)??null;
  try{const r=await api("/api/fam",{put});if(!r.ok)throw 0;const j=await r.json();
    S.share={on:true,id:j.id,code:j.code};S._sync={rev:j.rev,h:{}};for(const k in put)S._sync.h[k]=hs(JSON.stringify(put[k]));
    persist();keepURL();return true}catch(e){if(!quiet)toast("つながりませんでした。電波のよい所でもう一度押してください");return false}}
async function shPair(){if(!S.share.on&&!(await shStart()))return;
  S.shared=true;save();render(true);document.querySelector(".shc")?.setAttribute("open","");toast("共有リンクを作りました")}
async function shStop(){S.shared=false;save();await syncNow();if(await shStart(true)){S.shared=false;save();render(true);toast("共有をやめました")}else toast("つながりませんでした。電波のよい所でもう一度押してください")}
// iPhone は Safari とホーム画面のアプリで保存場所が別なので、URL に家族の鍵を入れておき、ホーム画面に追加したときに引き継ぐ
const isIOS=()=>"standalone" in navigator;
function keepURL(){if(!isIOS()||!S.share.on)return;const q="?f="+S.share.id+"."+S.share.code;
  if(!navigator.standalone&&location.search!==q)history.replaceState(null,"","/"+q);
  const m=document.querySelector('link[rel="manifest"]');if(m){const u=new URL(m.getAttribute("href"),location.origin);u.searchParams.set("f",S.share.id+"."+S.share.code);m.href=u.pathname+u.search}}
async function restoreFromURL(){const m=location.search.match(/[?&]f=([a-z0-9]{10})\.(\d{6})/);if(!m)return false;
  if(S.setup)return false;
  try{const r=await api("/api/fam/"+m[1]+"/sync",{code:m[2],rev:0,put:{}});if(!r.ok)return false;const j=await r.json();
    S._sync={rev:0,h:{}};applyUpd(j.upd||{});S._sync.rev=j.rev;S.share={on:true,id:m[1],code:m[2]};S.setup=1;persist();return true}catch(_){return false}}
const shText=()=>"うちの子手帳をふたりで使おう！リンクを開いて、あいことばを入れてね\n"+location.origin+"/j/"+S.share.id+"\nあいことば "+S.share.code;
