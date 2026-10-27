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
    const d=(await r.json()).data;for(const k of Object.keys(S))delete S[k];Object.assign(S,d);
    for(const k in defaults)if(S[k]===undefined)S[k]=JSON.parse(JSON.stringify(defaults[k]));
    S._sync=S._sync||{rev:0,h:{}};S.setup=1;persist();page=null;stack=[];
    const g=document.querySelector(".gate");if(g)ungate(g);render(false);toast("引き継ぎました");syncNow()}
  catch(_){toast("つながりませんでした。電波のよい所でもう一度押してください")}}
