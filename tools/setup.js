/* ===== はじめての画面・パートナーのあいことば ===== */
const chips=(name,L,cur)=>`<div class="kch">${L.map(([v,l])=>`<label><input type="radio" name="${name}" value="${v}"${cur===v?" checked":""}><span style="--kc:var(--ac)">${l}</span></label>`).join("")}</div>`;
function isStandalone(){try{return !!navigator.standalone||matchMedia("(display-mode: standalone)").matches}catch(_){return false}}
function gate(html){const o=document.createElement("div");o.className="gate";o.innerHTML=`<div class="gin">${html}</div>`;document.body.appendChild(o);document.documentElement.classList.add("gated");return o}
const ungate=o=>{o.remove();document.documentElement.classList.remove("gated");window.scrollTo(0,0)};
function setupGate(){
  const o=gate(`<div class="glogo">${pic("baby_face",72)}<h1>うちの子手帳</h1><p class="lead">はじめに少しだけ教えてください。あとから「メニュー」でいつでも変えられます。</p></div>
  ${isStandalone()?"":`<div class="sheet ga2h"><b>はじめる前に、ホーム画面に追加するのがおすすめです</b><p>アプリのようにすぐ開けて、通知も届くようになります。</p>${isIOS()?`<p><b>iPhone</b>：Safariの下にある共有ボタン（四角から矢印が出ている形）→「ホーム画面に追加」。追加したアイコンから開いて始めてください。</p><p class="sub">Safariとホーム画面のアイコンは、保存される場所が別です。先に追加してから入力すると、あとで移す手間がありません。</p>`:`<p><b>Android</b>：Chromeの右上の「︙」→「ホーム画面に追加」（または「アプリをインストール」）。</p>`}</div>`}
  <form class="sheet stack" id="gsetup">
   <div><b>いまは</b>${chips("mode",[["pre","妊娠中"],["mama","子育て中"]],"pre")}</div>
   <div><b>使う人</b>${chips("me",[["ママ","ママ"],["パパ","パパ"]],"ママ")}</div>
   <label><span id="gdl">出産予定日</span><input type="date" name="d" required></label>
   <label><span>赤ちゃんの名前 <span class="sub">（あとでOK）</span></span><input name="n" autocomplete="off"></label>
   <div id="gsex" hidden><b>性別</b>${chips("sex",[["girl","女の子"],["boy","男の子"]],"girl")}<p class="note" style="margin:4px 0 0">お宮参りや初節句の日にちを出すのに使います。</p></div>
   <p class="gerr" hidden></p>
   <button type="submit" class="pri">はじめる</button></form>
  <p class="note" style="text-align:center">パートナーから招待された人は、送られてきたリンクから開いてください。</p>
  <p style="text-align:center;margin:0"><button type="button" class="gpeek">入力しないで、中を見てみる</button></p>
  <details class="sheet gmv"><summary>${isIOS()&&navigator.standalone?"Safariで入れた内容を移す・機種変更した人はこちら":"機種変更した人はこちら"}</summary><p class="sub">前のスマホの「メニュー」→「共有と引き継ぎ」で出した、8文字のコードを入れてください。</p>
   <form class="add" id="gmv"><input name="c" placeholder="例：AB3K-9PQX" autocapitalize="characters" autocomplete="off" aria-label="引き継ぎコード"><button type="submit">引き継ぐ</button></form></details>`);
  o.querySelector(".gpeek").addEventListener("click",()=>{page=null;stack=[];ungate(o);render(false)});
  o.querySelector("#gmv").addEventListener("submit",e=>{e.preventDefault();e.stopPropagation();mvGet(e.target.c.value)});
  const f=o.querySelector("form"),sync=()=>{const pre=f.mode.value==="pre";o.querySelector("#gdl").textContent=pre?"出産予定日":"誕生日";o.querySelector("#gsex").hidden=pre};
  f.addEventListener("change",sync);sync();
  f.addEventListener("submit",e=>{e.preventDefault();const d=f.d.value;if(!d){const g=o.querySelector(".gerr");g.textContent="日にちを入れてください";g.hidden=false;return}
    S.mode=f.mode.value;S.me=f.me.value;S.name=f.n.value.trim();if(S.mode==="pre"){S.due=d;S.birth=d}else{S.birth=d;S.sex=f.sex.value}
    S.setup=1;page=null;stack=[];save();ungate(o);render(false);shStart(true)});
}
function joinGate(id){
  const o=gate(`<div class="glogo">${pic("baby_face",72)}<h1>うちの子手帳</h1><p class="lead">パートナーから招待されています。送られてきた「あいことば」を入れると、ふたりで同じ内容が見られます。</p></div>
  <form class="sheet stack" id="gjoin">
   <label>あいことば（6けたの数字）<input name="c" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" required class="gcode"></label>
   <div><b>あなたは</b>${chips("me",[["ママ","ママ"],["パパ","パパ"]],S.setup?S.me:"パパ")}</div>
   ${S.setup?`<p class="note" style="margin:0">このスマホに入れた内容は、パートナーの内容に置きかわります（「自分だけ」の予定は残ります）。</p>`:""}
   <p class="gerr" hidden></p>
   <button type="submit" class="pri">つなぐ</button></form>
  <button type="button" class="lk gskip">いまはやめておく</button>`);
  const f=o.querySelector("form"),err=t=>{const g=o.querySelector(".gerr");g.textContent=t;g.hidden=false},home=()=>history.replaceState(null,"","/");
  o.querySelector(".gskip").addEventListener("click",()=>{home();ungate(o);if(!S.setup)setupGate()});
  f.addEventListener("submit",async e=>{e.preventDefault();const c=f.c.value.replace(/\D/g,""),b=f.querySelector("[type=submit]");if(c.length!==6)return err("6けたの数字を入れてください");
    b.disabled=true;b.textContent="つないでいます…";
    try{const r=await api("/api/fam/"+id+"/sync",{code:c,rev:0,put:{}});
      if(r.status===403)return err("あいことばがちがいます。もう一度たしかめてください");
      if(r.status===429)return err("何回もまちがえたので、1時間ほどしてからもう一度ためしてください");
      if(r.status===404)return err("このリンクは見つかりませんでした。もう一度送ってもらってください");
      if(!r.ok)throw 0;const j=await r.json();
      S._sync={rev:0,h:{}};applyUpd(j.upd||{});S._sync.rev=j.rev;S.share={on:true,id,code:c};S.me=f.me.value;S.setup=1;
      page=null;stack=[];persist();home();keepURL();ungate(o);render(false);toast("つながりました");
    }catch(_){err("つながりませんでした。電波のよい所でもう一度押してください")}finally{b.disabled=false;b.textContent="つなぐ"}});
}
async function startGate(){
  const m=location.pathname.match(/^\/j\/([a-z0-9]{10})\/?$/);
  if(m){if(S.share.on&&S.share.id===m[1])history.replaceState(null,"","/");else{joinGate(m[1]);return}}
  const sp=location.pathname.match(/^\/([a-z]+)\/?$/),seo=sp&&typeof SEO_PAGES!=="undefined"&&SEO_PAGES[sp[1]]&&PAGES[sp[1]];
  pathReady=true;
  if(seo){page=sp[1];stack=[];render(false)}
  else if(location.pathname!=="/")history.replaceState(null,"","/");
  if(!S.setup&&await restoreFromURL()){page=null;stack=[];render(false);toast("前に入れた内容を引き継ぎました")}
  if(!S.setup&&!seo)return setupGate();
  if(!S.setup)return;
  if(!S.share.on)await shStart(true);
  keepURL();
}
/* ページごとのURL（Google検索用）。見ているページに合わせてURLと題名を変える */
let pathReady=false;
function syncPath(){if(!pathReady||typeof SEO_PAGES==="undefined"||/^\/j\//.test(location.pathname))return;const k=page&&SEO_PAGES[page]?page:"",want=k?"/"+k+"/":"/";
  document.title=k?SEO_PAGES[k]+"｜うちの子手帳":"うちの子手帳";
  if(location.pathname!==want)try{history.replaceState(history.state,"",want+location.search)}catch(_){}}
