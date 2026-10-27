/* ===== スマホへの通知（本番） ===== */
const pushCan=()=>"serviceWorker" in navigator&&"PushManager" in window&&"Notification" in window;
const devId=()=>{S.app=S.app||{ic:"baby_face",bg:0,n:{}};if(!S.app.mid){S.app.mid=[...crypto.getRandomValues(new Uint8Array(12))].map(x=>x.toString(16).padStart(2,"0")).join("");persist()}return S.app.mid};
const nOn=k=>{const d=(NOTI.find(x=>x[0]===k)||[])[2];return (S.app&&S.app.n&&S.app.n[k])??d};
const u8=s=>Uint8Array.from(atob(s.replace(/-/g,"+").replace(/_/g,"/")+"===".slice((s.length+3)%4)),c=>c.charCodeAt(0));
let pushBusy=false;
function pushUI(){const a=S.app||{};
  if(!pushCan())return `<p class="note">${isIOS()&&!navigator.standalone?"iPhoneは、Safariの共有ボタン →「ホーム画面に追加」で置いたアイコンから開くと、通知をオンにできます（iOS 16.4以降）。":"このブラウザでは通知が使えません。ChromeかSafariで開いてください。"}</p>`;
  if(Notification.permission==="denied")return `<p class="note">通知がブロックされています。スマホの「設定」で、このアプリ（またはブラウザ）の通知を許可してから、もう一度ためしてください。</p>`;
  if(a.push&&Notification.permission==="granted")return `<div class="pushon"><b>通知はオンです</b><span class="grow"></span><button type="button" class="lk" data-act="pushtest">ためしに1つ送る</button><button type="button" class="lk" data-act="pushoff">オフにする</button></div><p class="note">カレンダーの予定は、予定ごとに選んだ日（前日なら夜7時、当日なら朝7時）にお知らせします。${S.share.on?"":"パートナーが追加したときのお知らせは、「共有と引き継ぎ」でふたりをつなぐと届きます。"}</p>`;
  return `<button type="button" class="pladd" data-act="pushon"${pushBusy?" disabled":""}>${pushBusy?"準備しています…":"このスマホで通知をオンにする"}</button><p class="note">夫婦それぞれのスマホで、オンにしてください。</p>`}
async function pushOn(){if(pushBusy)return;pushBusy=true;render(true);
  try{if(await Notification.requestPermission()!=="granted")throw new Error("perm");
    const reg=await navigator.serviceWorker.ready,k=(await (await fetch("/api/push/key")).json()).k;
    let sub=await reg.pushManager.getSubscription();
    if(sub&&sub.options&&sub.options.applicationServerKey&&btoa(String.fromCharCode(...new Uint8Array(sub.options.applicationServerKey))).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"")!==k){await sub.unsubscribe();sub=null}
    if(!sub)sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:u8(k)});
    const r=await api("/api/push/sub",{dev:devId(),sub:sub.toJSON(),fam:S.share.on?S.share.id:null,code:S.share.on?S.share.code:null,who:S.me||"ママ",prefs:{shop:nOn("shop")}});
    if(!r.ok)throw new Error("srv");S.app.push=1;S.app.pushK="";persist();await pushSched();toast("通知をオンにしました")}
  catch(e){toast(e.message==="perm"?"通知が許可されませんでした":"うまくいきませんでした。電波のよいところでもう一度ためしてください")}
  finally{pushBusy=false;render(true)}}
async function pushOff(){try{const reg=await navigator.serviceWorker.ready,sub=await reg.pushManager.getSubscription();if(sub)await sub.unsubscribe()}catch(_){}
  api("/api/push/off",{dev:devId()}).catch(()=>{});S.app.push=0;persist();render(true);toast("通知をオフにしました")}
async function pushTest(){try{const r=await api("/api/push/test",{dev:devId()}),j=await r.json();toast(j.ok?"送りました。数秒で届きます":"送れませんでした。いったんオフにして、もう一度オンにしてください")}catch(_){toast("送れませんでした")}}
// これから出すお知らせを作る（このスマホの時計で計算）
function pushItems(){const out=[],now=Date.now(),lim=now+60*864e5;
  const at=(d,h,m)=>{const x=new Date(d);x.setHours(h,m||0,0,0);return x.getTime()};
  const add=(t,b,ms)=>{if(ms>now&&ms<lim)out.push({at:ms,t,b,u:"/"})};
  const md=d=>`${d.getMonth()+1}月${d.getDate()}日`;
  if(nOn("plan"))for(const p of S.plans||[]){if(!p.d||!p.r||p.r==="なし")continue;const d=new Date(p.d+"T00:00");
    const off={"当日の朝":0,"前日":1,"3日前":3,"1週間前":7}[p.r];if(off===undefined)continue;
    const w=off===0?"きょう":off===1?"あした":md(d);add("予定のお知らせ",`${w}${p.tm?" "+p.tm:""}　${p.t}`,off===0?at(d,7):at(addD(d,-off),19))}
  if(S.mode!=="pre"&&S.birth){let E=[];try{E=events().filter(e=>!S.done[e.id])}catch(_){}
    for(const e of E){if(nOn("vac")&&(e.cat==="予防接種"||e.cat==="健診"))add("予防接種・健診",`あしたは「${e.title}」の目安の日です。予約がまだなら、早めに入れておきましょう`,at(addD(e.date,-1),19));
      if(nOn("ev")&&(e.cat==="行事"||e.cat==="手続き"))add(e.cat==="手続き"?"手続きのお知らせ":"行事のお知らせ",`「${e.title}」の目安まで、あと1週間です（${md(e.date)}）`,at(addD(e.date,-7),10));
      if(nOn("gift")&&e.id==="uchi"&&(S.gifts||[]).some(g=>!g.sent))for(const n of [7,0])add("内祝い",`まだお返ししていない内祝いがあります${n?"（目安まであと1週間）":"（きょうが目安です）"}`,at(addD(e.date,-n),10))}}
  if(nOn("chore"))for(let i=0;i<14;i++)add("きょうの家事",(S.chores||[]).length?"きょうの家事、終わったものにはんこを押しておきましょう":"きょうもおつかれさまです",at(addD(T0,i),20));
  return out.sort((a,b)=>a.at-b.at).slice(0,150)}
let pushT=null;
async function pushSched(){const a=S.app;if(!a||!a.push)return;const it=pushItems(),meta={fam:S.share.on?S.share.id:null,code:S.share.on?S.share.code:null,who:S.me||"ママ",prefs:{shop:nOn("shop")}},key=String(hs(JSON.stringify([it,meta])));if(a.pushK===key)return;
  try{const r=await api("/api/push/sched",Object.assign({dev:devId(),items:it},meta));if(r.ok){const j=await r.json();if(j.error==="not_found"){a.push=0}else a.pushK=key;persist()}}catch(_){}}
{const r1=render;render=function(k){r1(k);clearTimeout(pushT);pushT=setTimeout(pushSched,3000)}}
