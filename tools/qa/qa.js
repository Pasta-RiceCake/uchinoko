// 全テーマ×妊娠中/子育て中×絵2種で、全画面を開いて調べる
const {chromium}=require('playwright');
const THS=process.argv[2].split(',');const URL=process.argv[3]||'http://127.0.0.1:8798/';
(async()=>{const b=await chromium.launch();const out=[];
for(const th of THS){
 const p=await b.newPage({viewport:{width:390,height:844}});let errs=[];
 p.on('pageerror',e=>errs.push(e.message));p.on('console',m=>{if(m.type()==='error'&&!/Failed to load resource|net::|fonts/.test(m.text()))errs.push('console:'+m.text())});
 await p.goto(URL);await p.waitForTimeout(1200);
 const cl=async(a,v)=>{await p.evaluate(([a,v])=>{const x=document.createElement('button');x.dataset.act=a;x.dataset.v=v;document.body.appendChild(x);x.click();x.remove()},[a,v]);await p.waitForTimeout(250)};
 await cl('th',th);
 for(const mode of ['pre','post']){
  await cl('mode',mode);
  for(const icm of ['theme','line']){
   await cl('ils',icm);
   const pages=require('./qa_pages.json');
   const tabs=await p.$$eval('nav.tabs button',bs=>bs.length);
   const list=[...Array(tabs).keys()].map(i=>['tab',i]).concat((icm==='theme'?pages:pages.slice(0,6)).map(k=>['open',k]));
   for(const [kind,v] of list){
    errs=[];
    if(kind==='tab'){await p.click(`nav.tabs button:nth-child(${v+1})`);await p.waitForTimeout(350)}else{await cl('open',v);await p.waitForTimeout(150)}
    const r=await p.evaluate(()=>{
     const W=innerWidth,iss=[];
     if(document.documentElement.scrollWidth>W+1)iss.push('横はみ出し '+document.documentElement.scrollWidth);
     const wide=[...document.querySelectorAll('main *, .page *, body *')].filter(e=>{const b=e.getBoundingClientRect();return b.width>0&&b.right>W+2&&getComputedStyle(e).position!=='fixed'&&!e.closest('[style*="overflow"],.scx,.hs')}).slice(0,3).map(e=>e.tagName+'.'+e.className);
     if(wide.length&&document.documentElement.scrollWidth>W+1)iss.push('はみ出す要素 '+wide.join(' '));
     const bad=[...document.images].filter(i=>i.complete&&i.naturalWidth===0&&i.src&&!i.classList.contains('a8px')&&!/a8\.net|rakuten/.test(i.src)).map(i=>i.getAttribute('alt')||i.src.slice(0,40));
     if(bad.length)iss.push('絵が出ない '+bad.length);
     const ph=document.querySelectorAll('.pvph').length;
     // 字の読みにくさ：文字色と、うしろの面の色（単色のとき）
     const lum=c=>{const sr=/^color\(srgb/.test(c);const m=c.match(/[\d.]+/g);if(!m)return null;const [r,g,b]=m.slice(0,3).map(x=>{x=sr?+x:x/255;return x<=.03928?x/12.92:Math.pow((x+.055)/1.055,2.4)});return {L:.2126*r+.7152*g+.0722*b,a:m[3]===undefined?1:+m[3]}};
     const low=[];
     for(const e of document.querySelectorAll('body *')){
      if(!e.childNodes.length||![...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim().length>1))continue;
      const cs=getComputedStyle(e);if(cs.visibility==='hidden'||cs.display==='none'||+cs.opacity<.5)continue;
      const bx=e.getBoundingClientRect();if(bx.width===0||bx.height===0)continue;
      if(cs.webkitTextFillColor&&/rgba\(0, 0, 0, 0\)/.test(cs.webkitTextFillColor))continue;
      const fg=lum(cs.webkitTextFillColor&&cs.webkitTextFillColor!==cs.color?cs.webkitTextFillColor:cs.color);if(!fg||fg.a<.5)continue;
      let n=e,bg=null;
      while(n&&n.nodeType===1){const s=getComputedStyle(n);if(s.backgroundImage&&s.backgroundImage!=='none'){bg='img';break}const l=lum(s.backgroundColor);if(l&&l.a>.85){bg=l;break}n=n.parentElement}
      if(!bg||bg==='img')continue;
      const cr=(Math.max(fg.L,bg.L)+.05)/(Math.min(fg.L,bg.L)+.05);
      if(cr<3)low.push(e.textContent.trim().slice(0,14)+'('+cr.toFixed(1)+')');
     }
     if(low.length)iss.push('字が薄い '+low.slice(0,4).join(' / ')+(low.length>4?` ほか${low.length-4}`:''));
     return iss});
    if(errs.length)r.push('エラー '+[...new Set(errs)].slice(0,2).join(' | '));
    if(r.length)out.push([th,mode,icm,kind==='tab'?'tab'+v:v,r.join(' ; ')]);
    if(kind==='open'){await p.evaluate(()=>{const x=document.querySelector('[data-act="back"],.back');if(x)x.click()});await p.waitForTimeout(100)}
   }
  }
 }
 await p.close();console.error('done',th);
}
require('fs').writeFileSync('qa_'+THS[0]+'.json',JSON.stringify(out,null,0));await b.close()})();
