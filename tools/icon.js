/* ===== ホーム画面のアイコン（えらんだイラストと背景色） ===== */
let icBusy=false;
function icLinks(id){
  const set=(rel,href)=>{let l=document.querySelector(`link[rel="${rel}"]`);if(!l){l=document.createElement("link");l.rel=rel;document.head.appendChild(l)}if(l.getAttribute("href")!==href)l.href=href};
  set("apple-touch-icon","/i/"+id+".png");set("icon","/i/"+id+".png");if(!isIOS())set("manifest","/m/"+(S.app.mid||id)+".webmanifest");keepURL();
}
function icDraw(a){return new Promise((ok,ng)=>{const own=a.ic==="own"&&a.own,src=own?a.own:(imgSrc(a.ic,a.ics)||IMG[a.ic]);if(!src)return ng();
  const im=new Image();im.onload=()=>{const N=512,c=document.createElement("canvas");c.width=c.height=N;const g=c.getContext("2d");
    g.fillStyle=APPBG[a.bg]||"#fff";g.fillRect(0,0,N,N);
    if(own)g.drawImage(im,0,0,N,N);else{const s=N*.68,r=s/Math.max(im.width,im.height),w=im.width*r,h=im.height*r;g.drawImage(im,(N-w)/2,(N-h)/2,w,h)}
    ok(c.toDataURL("image/png"))};im.onerror=ng;im.src=src})}
async function iconSync(){const a=S.app;if(!a||!a.ic)return;
  // Android はこの番号の置き場所を見に来るので、アイコンを変えてもホームの絵が新しくなる
  if(!a.mid){a.mid=[...crypto.getRandomValues(new Uint8Array(12))].map(x=>x.toString(16).padStart(2,"0")).join("");persist()}
  if(a.ic!=="own"&&!a.ics)a.ics=ilSet();
  if(a.ic!=="own"&&!imgSrc(a.ic,a.ics))return;
  const key=a.ic+":"+(a.ics||"")+":"+a.bg+":"+(a.ic==="own"?hs(a.own||""):"");
  if(a.icK===key&&a.icId)return icLinks(a.icId);
  if(icBusy)return;icBusy=true;
  try{const png=(await icDraw(a)).split(",")[1],r=await api("/api/icon",{png,mid:a.mid});if(!r.ok)throw 0;const j=await r.json();
    a.icK=key;a.icId=j.id;persist();icLinks(j.id)}catch(_){}finally{icBusy=false}}
{const r0=render;render=function(k){r0(k);iconSync()}}
