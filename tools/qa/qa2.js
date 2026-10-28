// 動き・機能・画面の行き来：各画面のボタンを全部押す、入力する、戻る
const {chromium}=require('playwright');const fs=require('fs');
const MODE=process.argv[2],TH=process.argv[3]||'app',URL=process.argv[4]||'http://127.0.0.1:8798/';
const pages=require('./qa_pages.json');
(async()=>{const b=await chromium.launch();const ctx=await b.newContext({viewport:{width:390,height:844}});const p=await ctx.newPage();
let errs=[];p.on('pageerror',e=>errs.push(e.message));p.on('dialog',d=>d.dismiss());
p.on('popup',pp=>pp.close());
const out=[];const note=(pg,what,msg)=>out.push([MODE,TH,pg,what,msg]);
const cl=async(a,v)=>{await p.evaluate(([a,v])=>{const x=document.createElement('button');x.dataset.act=a;x.dataset.v=v;document.body.appendChild(x);x.click();x.remove()},[a,v]);await p.waitForTimeout(200)};
const fresh=async()=>{await p.goto(URL);await p.evaluate(()=>localStorage.clear());await p.goto(URL);await p.waitForTimeout(700);
 if(await p.$('.gate input[name=d]')){await p.fill('.gate input[name=d]','2026-11-17');await p.click('.gate .pri');await p.waitForTimeout(500)}
 await cl('th',TH);await cl('mode',MODE)};
const title=()=>p.evaluate(()=>{const h=document.querySelector('.ph h1,main h1');return h?h.textContent.trim():''});
const sane=async(pg,what)=>{const r=await p.evaluate(()=>({w:document.documentElement.scrollWidth,t:(document.querySelector('main')||document.body).innerText.trim().length}));
 if(r.w>391)note(pg,what,'横はみ出し '+r.w);if(r.t<20)note(pg,what,'画面がほぼ空');if(errs.length){note(pg,what,'エラー '+[...new Set(errs)].slice(0,2).join(' | '));errs=[]}};
for(const pg of pages){
 await fresh();
 // 行き来：メニューから開く→戻る
 await p.click('nav.tabs button:last-child');await p.waitForTimeout(300);
 const via=await p.$(`.menu-g [data-act="open"][data-v="${pg}"]`);
 if(via){await via.click();await p.waitForTimeout(300)}else{await cl('open',pg)}
 const t0=await title();await sane(pg,'開く');
 const back=await p.$('[data-act="back"]');
 if(!back){if(!['cal','chores','shop'].includes(pg))note(pg,'戻る','戻るボタンがない')}
 else{await back.click();await p.waitForTimeout(300);const t1=await title();if(t1===t0&&t0)note(pg,'戻る','戻っても同じ画面 '+t0);await sane(pg,'戻る')}
 // ボタンを全部押す
 await cl('open',pg);await p.waitForTimeout(250);
 const n=await p.evaluate(()=>{const els=[...document.querySelectorAll('main button,main [data-act],main summary,main label')].filter(e=>!e.closest('nav.tabs')&&e.getBoundingClientRect().width>0);window.__qa=els.map((e,i)=>{e.dataset.qa=i;return i});return els.length});
 const lab=[];for(let i=0;i<n;i++)lab.push(await p.evaluate(i=>{const e=document.querySelector(`[data-qa="${i}"]`);return e?((e.dataset.act||e.tagName)+':'+(e.dataset.v||'')+':'+e.textContent.trim().slice(0,12)):null},i));
 let clicked=0;
 for(let i=0;i<Math.min(n,90);i++){
  if(!lab[i])continue;if(/^(back|share|open):/.test(lab[i])&&!/^open:/.test(lab[i]))continue;
  await cl('open',pg);await p.waitForTimeout(120);
  // 同じ並びをもう一度つける
  await p.evaluate(()=>{const els=[...document.querySelectorAll('main button,main [data-act],main summary,main label')].filter(e=>!e.closest('nav.tabs')&&e.getBoundingClientRect().width>0);els.forEach((e,i)=>e.dataset.qa=i)});
  const el=await p.$(`[data-qa="${i}"]`);if(!el)continue;
  try{await el.evaluate(x=>x.scrollIntoView({block:"center"}));await el.click({timeout:1200});clicked++}catch(e){try{await el.evaluate(x=>x.click());clicked++}catch(e2){continue}}
  await p.waitForTimeout(180);await sane(pg,'押す '+lab[i]);
 }
 // 入力する
 await cl('open',pg);await p.waitForTimeout(200);
 const ins=await p.$$('main input:not([type=file]):not([type=hidden]),main textarea,main select');
 for(const e of ins){try{const tp=await e.evaluate(x=>x.tagName==='SELECT'?'select':x.type);
  if(tp==='select'){await e.selectOption({index:1}).catch(()=>{})}
  else if(tp==='checkbox'||tp==='radio'){await e.click({force:true,timeout:800})}
  else if(tp==='date'){await e.fill('2026-12-01')}else if(tp==='time'){await e.fill('09:30')}else if(tp==='number'){await e.fill('3')}
  else await e.fill('テスト');await e.press('Enter').catch(()=>{});await p.waitForTimeout(80)}catch(x){}}
 await sane(pg,'入力');
 // リンク
 const bad=await p.evaluate(()=>[...document.querySelectorAll('main a')].filter(a=>{const h=a.getAttribute('href')||'';return !h||h==='#'||/undefined|null/.test(h)||(/^https?:/.test(h)&&a.target!=='_blank')}).map(a=>a.textContent.trim().slice(0,14)+' '+(a.getAttribute('href')||'').slice(0,40)));
 if(bad.length)note(pg,'リンク','おかしいリンク '+bad.slice(0,3).join(' / '));
 note(pg,'件数',`ボタン${n}個中${clicked}個を押した・入力${ins.length}個`);
 console.error('done',pg);
}
// タブ
await fresh();for(let i=1;i<=4;i++){await p.click(`nav.tabs button:nth-child(${i})`);await p.waitForTimeout(300);await sane('tab'+i,'タブ')}
// 保存（読みこみ直しても残るか）
await fresh();const before=await p.evaluate(()=>localStorage.length);await p.reload();await p.waitForTimeout(600);
const th=await p.evaluate(()=>document.documentElement.dataset.th);if(th!==TH)note('保存','読みこみ直し','テーマが残らない '+th);
fs.writeFileSync(`qa2_${MODE}_${TH}.json`,JSON.stringify(out));await b.close()})();
