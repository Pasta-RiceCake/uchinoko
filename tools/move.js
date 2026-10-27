/* ===== 共有と引き継ぎ（せってい） ===== */
let mvCode=null,mvArm=false;
const mvFmt=c=>c.slice(0,4)+"-"+c.slice(4);
function vSync(){
  return head("共有と引き継ぎ","hearthands","mint")+`<div class="sec-t">パートナーと共有</div>${shareCard()}
  <div class="sec-t">機種変更の引き継ぎ</div>
  <div class="sheet stack"><div><b>前のスマホで</b><div class="sub">ボタンを押すと、8文字の引き継ぎコードが出ます。コードは24時間のあいだ、1回だけ使えます。</div></div>
   ${mvCode?`<div class="mvcode">${mvFmt(mvCode)}</div><button type="button" class="btn" data-act="mvcopy">コードをコピー</button>`:`<button type="button" class="pri mvbtn" data-act="mvput">引き継ぎコードを出す</button>`}</div>
  <div class="sheet stack" style="margin-top:12px"><div><b>新しいスマホで</b><div class="sub">前のスマホで出したコードを入れてください。このスマホに入っている内容は、前のスマホの内容に置きかわります。</div></div>
   <form class="add" data-form="mvget"><input name="c" placeholder="例：AB3K-9PQX" autocapitalize="characters" autocomplete="off" aria-label="引き継ぎコード"><button type="submit">引き継ぐ</button></form></div>
  <div class="sec-t">バックアップ</div>
  <div class="sheet stack"><div><b>ファイルに保存</b><div class="sub">いま入っている内容を、まるごと1つのファイルにしてスマホに保存します。月に1回くらい保存しておくと安心です。ファイルには記録がすべて入っているので、人には送らないでください。${S.bkAt?"<br>前に保存した日："+esc(S.bkAt):""}</div></div>
   <button type="button" class="pri mvbtn" data-act="bksave">バックアップを保存する</button>
   <div><b>ファイルから戻す</b><div class="sub">保存したファイルを選ぶと、その時の内容に戻ります。いまの内容は置きかわります。</div></div>
   <label class="btn bkin">ファイルを選ぶ<input type="file" accept=".json,application/json" data-act="bkload" hidden></label></div>
  <p class="note">パートナーと共有しているなら、新しいスマホで共有リンクを開いてあいことばを入れるだけでも、ふたりの内容は戻ります（「自分だけ」の予定やきせかえは、引き継ぎコードで移してください）。</p>`;
}
async function mvPut(){toast("コードを作っています…");
  try{const r=await api("/api/move",{data:S});if(!r.ok)throw 0;mvCode=(await r.json()).code;render(true)}
  catch(_){toast("つながりませんでした。電波のよい所でもう一度押してください")}}
async function mvGet(c,form){c=String(c||"").toUpperCase().replace(/[^A-Z0-9]/g,"");
  if(c.length!==8)return toast("8文字のコードを入れてください");
  if(S.setup&&!mvArm){mvArm=true;setTimeout(()=>{mvArm=false},6000);return toast("内容が置きかわります。もう一度押すと引き継ぎます")}
  mvArm=false;
  try{const r=await api("/api/move/get",{code:c});if(r.status===404)return toast("コードが見つかりません。24時間すぎたか、もう使われています");if(!r.ok)throw 0;
    mvApply((await r.json()).data);toast("引き継ぎました");syncNow()}
  catch(_){toast("つながりませんでした。電波のよい所でもう一度押してください")}}

function mvApply(d){for(const k of Object.keys(S))delete S[k];Object.assign(S,d);
  for(const k in defaults)if(S[k]===undefined)S[k]=JSON.parse(JSON.stringify(defaults[k]));
  S._sync=S._sync||{rev:0,h:{}};S.setup=1;persist();page=null;stack=[];
  const g=document.querySelector(".gate");if(g)ungate(g);render(false)}
// バックアップ：ファイルに保存・ファイルから戻す
async function bkSave(){const d=new Date(),day=d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0");
  const o=JSON.parse(JSON.stringify(S));delete o._sync;
  const name="うちの子手帳_"+day+".json",blob=new Blob([JSON.stringify({app:"uchinoko",v:1,at:d.toISOString(),data:o})],{type:"application/json"});
  try{const f=new File([blob],name,{type:"application/json"});
    if(navigator.canShare&&navigator.canShare({files:[f]})){await navigator.share({files:[f],title:name});}
    else{const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=name;document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},1000)}
    S.bkAt=day.replace(/-/g,"/");persist();render(true);toast("保存しました")}
  catch(e){if(e&&e.name==="AbortError")return;toast("保存できませんでした")}}
let bkArm=null;
function bkLoad(el){const fl=el.files&&el.files[0];if(!fl)return;const r=new FileReader();
  r.onload=()=>{let j;try{j=JSON.parse(r.result)}catch(_){j=null}el.value="";
    if(!j||j.app!=="uchinoko"||!j.data)return toast("うちの子手帳のバックアップではないようです");
    if(S.setup&&bkArm!==fl.name){bkArm=fl.name;setTimeout(()=>{bkArm=null},8000);return toast("内容が置きかわります。もう一度同じファイルを選ぶと戻します")}
    bkArm=null;const keep=S.share;mvApply(j.data);if(keep&&keep.on){S.share=keep}S._sync={rev:S._sync?.rev||0,h:{}};persist();
    toast((j.at||"").slice(0,10).replace(/-/g,"/")+"の内容に戻しました");syncNow()};
  r.readAsText(fl)}
