// ページごとの HTML に、最初から中身を書いておく（Google が読みやすいように）
// 使い方: node tools/prerender.js   （real.py の最後から呼ばれる）
const {chromium}=require('playwright');const fs=require('fs'),path=require('path');
const PUB=path.join(__dirname,'..','public');
const walk=(d,r='')=>fs.readdirSync(d,{withFileTypes:true}).filter(x=>x.isDirectory()&&!['a','data','ill','dl'].includes(x.name)||false).flatMap(x=>{const rr=r+x.name+'/';return (fs.existsSync(path.join(d,x.name,'.page'))?[rr.slice(0,-1)]:[]).concat(walk(path.join(d,x.name),rr))});
const pages=walk(PUB);
const TYPES={'.html':'text/html','.js':'text/javascript','.json':'application/json','.webp':'image/webp','.png':'image/png','.css':'text/css','.webmanifest':'application/manifest+json'};
(async()=>{const b=await chromium.launch();const c=await b.newContext({viewport:{width:390,height:844}});
 await c.route('http://pre.local/**',r=>{const u=new URL(r.request().url());let f=path.join(PUB,decodeURIComponent(u.pathname));
  if(fs.existsSync(f)&&fs.statSync(f).isDirectory())f=path.join(f,'index.html');
  if(!fs.existsSync(f))return r.fulfill({status:404,body:''});
  r.fulfill({status:200,body:fs.readFileSync(f),contentType:TYPES[path.extname(f)]||'application/octet-stream'})});
 await c.route(/^https?:\/\/(?!pre\.local)/,r=>r.abort());
 let n=0;
 for(const k of pages){const p=await c.newPage();
  try{await p.goto('http://pre.local/'+k+'/');await p.waitForTimeout(700);
   const html=await p.evaluate(()=>{const m=document.getElementById('main');m.querySelectorAll('[hidden]').forEach(e=>e.remove());return m.innerHTML});
   const f=path.join(PUB,k,'index.html');const s=fs.readFileSync(f,'utf8');
   if(html&&s.includes('<main id="main"></main>')){fs.writeFileSync(f,s.replace('<main id="main"></main>','<main id="main">'+html+'</main>'));n++}
  }catch(e){console.error('skip',k,e.message.slice(0,80))}
  await p.close()}
 await b.close();console.log('prerender',n,'/',pages.length)})();
