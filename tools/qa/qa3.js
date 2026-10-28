// 機能テスト：フォームに書いて送る→画面に出るか・読みこみ直しても残るか／チェック→残るか／消す→減るか
const {chromium}=require('playwright');const fs=require('fs');
const MODE=process.argv[2]||'post',URL=process.argv[3]||'http://127.0.0.1:8798/';
const pages=require('./qa_pages.json');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:390,height:844}});
let errs=[];p.on('pageerror',e=>errs.push(e.message));p.on('dialog',d=>d.accept());
const out=[];const ok=[];const note=(pg,w,m)=>out.push([MODE,pg,w,m]);
const cl=async(a,v)=>{await p.evaluate(([a,v])=>{const x=document.createElement('button');x.dataset.act=a;x.dataset.v=v;document.body.appendChild(x);x.click();x.remove()},[a,v]);await p.waitForTimeout(250)};
const fresh=async()=>{await p.goto(URL);await p.evaluate(()=>localStorage.clear());await p.goto(URL);await p.waitForTimeout(700);
 if(await p.$('.gate input[name=d]')){await p.fill('.gate input[name=d]','2026-11-17');await p.click('.gate .pri');await p.waitForTimeout(500)}
 await cl('mode',MODE)};
const txt=()=>p.evaluate(()=>(document.querySelector('main')||document.body).innerText);
for(const pg of pages){
 await fresh();await cl('open',pg);
 const nf=await p.$$eval('main form',f=>f.length);
 for(let fi=0;fi<nf;fi++){
  await cl('open',pg);const forms=await p.$$('main form');const f=forms[fi];if(!f)continue;
  const vis=await f.evaluate(x=>x.getBoundingClientRect().height>0&&!x.closest('details:not([open])'));
  if(!vis){const s=await f.evaluate(x=>{const d=x.closest('details');if(d){d.open=true;return 1}return 0});if(!s)continue}
  const tok='テスト'+pg+fi;
  const ins=await f.$$('input:not([type=hidden]):not([type=file]),textarea,select');let wrote=false;
  for(const e of ins){const tp=await e.evaluate(x=>x.tagName==='SELECT'?'select':(x.type||'text'));
   try{if(tp==='select'){const n=await e.evaluate(x=>x.options.length);if(n>1)await e.selectOption({index:1})}
   else if(tp==='date')await e.fill('2026-12-01');else if(tp==='time')await e.fill('09:30');else if(tp==='number')await e.fill('3000');
   else if(tp==='checkbox'||tp==='radio'){}
   else if(tp==='url')await e.fill('https://example.com/');else if(tp==='tel')await e.fill('0312345678');
   else if(!wrote){await e.fill(tok);wrote=true}else await e.fill('メモ')}catch(x){}}
  const sb=await f.$('button[type=submit],button:not([type])');
  if(!sb){note(pg,'フォーム'+fi,'送るボタンがない');continue}
  errs=[];await sb.evaluate(x=>x.scrollIntoView({block:"center"}));await sb.click({timeout:2000}).catch(()=>sb.evaluate(x=>x.click()));await p.waitForTimeout(400);
  if(errs.length)note(pg,'フォーム'+fi,'エラー '+errs[0]);
  const t1=await txt();const inp=await p.evaluate(t=>[...document.querySelectorAll('input,textarea')].some(i=>i.value===t),tok);
  if(!wrote)continue;
  if(!t1.includes(tok)&&!inp){note(pg,'フォーム'+fi,'書いたものが画面に出ない');continue}
  await p.reload();await p.waitForTimeout(700);await cl('mode',MODE);await cl('open',pg);
  const t2=await txt();const inp2=await p.evaluate(t=>[...document.querySelectorAll('input,textarea')].some(i=>i.value===t),tok);
  if(!t2.includes(tok)&&!inp2)note(pg,'フォーム'+fi,'読みこみ直すと消える');else ok.push(pg+':フォーム'+fi);
 }
 // チェック
 await fresh();await cl('open',pg);
 const nck=await p.$$eval('main input[type=checkbox][data-act]',x=>x.length);
 if(nck){const k=await p.$('main input[type=checkbox][data-act]');const before=await k.isChecked();const key=await k.evaluate(x=>x.dataset.act+':'+(x.dataset.i||x.dataset.v||''));
  errs=[];await k.evaluate(x=>x.scrollIntoView({block:"center"}));await k.click({timeout:2000}).catch(()=>k.evaluate(x=>x.click()));await p.waitForTimeout(350);if(errs.length)note(pg,'チェック','エラー '+errs[0]);
  await p.reload();await p.waitForTimeout(700);await cl('mode',MODE);await cl('open',pg);
  const now=await p.evaluate(key=>{const [a,i]=key.split(':');const e=[...document.querySelectorAll(`main input[type=checkbox][data-act="${a}"]`)].find(x=>(x.dataset.i||x.dataset.v||'')===i);return e?e.checked:null},key);
  if(now===before)note(pg,'チェック','チェックが残らない '+key);else ok.push(pg+':チェック')}
 // 消す
 await fresh();await cl('open',pg);
 const del=await p.$('main button.x,main [data-act$="del"]');
 if(del){const a=await del.evaluate(x=>x.dataset.act);const c0=await p.$$eval(`main [data-act="${a}"]`,x=>x.length);
  errs=[];await del.evaluate(x=>x.scrollIntoView({block:"center"}));await del.click({timeout:2000}).catch(()=>del.evaluate(x=>x.click()));await p.waitForTimeout(350);if(errs.length)note(pg,'消す','エラー '+errs[0]);
  const c1=await p.$$eval(`main [data-act="${a}"]`,x=>x.length);if(c1>=c0)note(pg,'消す','消しても減らない '+a+' '+c0+'→'+c1);else ok.push(pg+':消す')}
 console.error('done',pg);
}
fs.writeFileSync(`qa3_${MODE}.json`,JSON.stringify({out,ok}));await b.close()})();
