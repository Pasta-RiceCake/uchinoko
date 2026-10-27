# 見本（tools/proto.html）から本番の public/index.html を作る。
# 使い方: python3 tools/real.py
import os, re, base64, io
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(ROOT, 'tools/proto.html'), encoding='utf-8').read()

def rep(old, new, n=1):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, n)

# ---- 保存キーと見本データ ----
rep('const KEY="uchinoko-v7";', 'const KEY="uchinoko-live";')
rep('name:"ひなた",birth:iso(addD(T0,-42)),sex:"girl",', 'name:"",birth:iso(T0),sex:"girl",')
rep('shop:[{t:"おむつ（新生児用 → Sサイズ）",d:false},{t:"おしりふき 詰めかえ",d:false},{t:"粉ミルク",d:true}],', 'shop:[],')
rep('done:{shusshou:true,jidou:true,hoken:true,oshichiya:true,m1:true},', 'done:{},')
rep('plans:[{d:iso(addD(T0,3)),t:"パパの実家に顔見せ"},{d:iso(addD(T0,9)),t:"ママ 産後の歯医者"}],', 'plans:[],')
s = re.sub(r'gifts:\[\{who:"山田のおばあちゃん".*?\],\n', 'gifts:[],\n', s, count=1, flags=re.S)
s = re.sub(r'contacts:\[\["かかりつけの小児科".*?\]\],\n', 'contacts:[["かかりつけの小児科",""],["夜間・休日の病院",""],["保育園",""],["保険証・医療証のある場所",""],["アレルギー・持病",""],["ママの携帯",""],["パパの携帯",""]],\n', s, count=1, flags=re.S)
s = re.sub(r'visits:\[\{d:iso\(addD\(T0,-12\)\).*?\],\n', 'visits:[],\n', s, count=1, flags=re.S)
rep('wants:[{t:"スワドル（くるむおくるみ）",m:"友達のおすすめ。Sサイズ（例）"}]', 'wants:[]')
rep('list:[{y:"ひなた",k:"陽向",by:"パパ",l:{パパ:true}},{y:"さくら",k:"咲良",by:"ママ",l:{ママ:true}}]', 'list:[]')
rep('day:[["7:00","起きる・ミルク"],["10:00","ミルク"],["13:00","お昼寝"]]', 'day:[]')
s = re.sub(r'n:\[\{h:"陣痛が来たら".*?\]\};return S\.ff\}', 'n:[]};return S.ff}', s, count=1, flags=re.S)
assert 'n:[]};return S.ff}' in s
# 見本用の「相手のはんこ」は入れない
rep('  try{seedChore()}catch(_){}\n', '')

# ---- 名前候補: 共有中は自分のスマホの「使う人」で♡ ----
rep('function vNames(){const n=nmS(),me=n.me,', 'const nmMe=()=>S.share.on?(S.me||"ママ"):nmS().me;\nfunction vNames(){const n=nmS(),me=nmMe(),')
rep('n.list.push({y:v("y"),k:v("k"),by:n.me,l:{[n.me]:true}})', 'n.list.push({y:v("y"),k:v("k"),by:nmMe(),l:{[nmMe()]:true}})')
s = s.replace('nmS().me', 'nmMe()').replace('const nmMe=()=>S.share.on?(S.me||"ママ"):nmMe();', 'const nmMe=()=>S.share.on?(S.me||"ママ"):nmS().me;')
s = s.replace('else if(a==="nmme")nmMe()=el.value;', 'else if(a==="nmme")nmS().me=el.value;')
rep('<div class="sheet"><div class="kch" style="justify-content:center">${["ママ","パパ"].map(w=>`<label><input type="radio" name="nmme"',
    '${S.share.on?"":`<div class="sheet"><div class="kch" style="justify-content:center">`+["ママ","パパ"].map(w=>`<label><input type="radio" name="nmme"')
rep('${w}として選ぶ</span></label>`).join("")}</div><p class="note" style="text-align:center;margin:6px 0 0">本番ではそれぞれのスマホで選べます。相手の♡は、ふたりともつけるまで見えません。</p></div>',
    '${w}として選ぶ</span></label>`).join("")+`</div><p class="note" style="text-align:center;margin:6px 0 0">パートナーと共有すると、それぞれのスマホで♡をつけられます。</p></div>`}')

# ---- 見本の注意書きを本番向けに ----
rep('<p class="note">${esc(at)}で探します。本番では、近くのイベントをこのページの中に出したいです。</p>', '<p class="note">${esc(at)}で探します。</p>')
rep('<p class="note">いま出ているのは見本の例です。本番では、各スポットの公式サイトのイベント情報を集めて出す予定です。</p>', '<p class="note">イベントは例です。行く前に、各スポットの公式サイトで確かめてください。</p>')
rep('<p class="note">このページの中に地図の結果を出すのは、本番のサイトでできるようにします（見本では外の地図を開く形です）。</p>', '')
rep('本番では、市区町村ごとの公式ページに直接つながるようにしたいです。', '')
rep('いまは見本の例です。本番では、楽天の売れ筋ランキングを週に1回自動で取ってきて入れ替えます。', '')
rep('（本番のサイトで使えます）', '')
rep('通知は、ホーム画面に追加したあとに届きます（iPhoneはiOS 16.4以降）。見本では届きません。', 'スマホへの通知は、これからつけます。それまでは、近い予定がホームのいちばん上に出ます。')
rep('<div class="sub" style="margin-top:6px">※ 見本なので、実際に相手の画面に出るのは本番からです。</div>', '')
rep('今は見本の園です。本番では、位置情報をオンにすると国土交通省の全国の保育所データから近くの園を出し、空き状況（○あり △少し ×なし）は、各自治体が毎月出している情報にリンクします。', '園の一覧は例です。近くの園と空き状況は、地図や自治体の「入園のしおり」で確かめてください。')
rep('今は見本です。本番では評判のよい物を調べて入れます。', '')
rep('<p class="note">本番では、このページをリンクで送れます（相手はログインなしで見られます）。</p>', '')
rep('case"share":toast("本番では、合言葉つきのリンクが出ます");break;', 'case"share":open("fufu");break;')
rep('case"hkloc":toast("本番では、位置情報をオンにすると近くの園が出ます");break;', 'case"hkloc":window.open("https://www.google.com/maps/search/"+encodeURIComponent("保育園 "+S.pref+(S.city||"")),"_blank","noopener");break;')
s = re.sub(r'function vShareInfo\(\)\{return vFufu\(\);.*?\n\}\n', 'function vShareInfo(){return vFufu()}\n', s, count=1, flags=re.S)
assert '本番' not in s and '見本' not in s, [m.start() for m in re.finditer('本番|見本', s)]

# ---- 共有リンク ----
rep('<code>https://uchinoko-techo.example/j/${s.id}</code>', '<code>${location.origin}/j/${s.id}</code>')
rep('<div class="sub">あいことば <b class="code">${s.code}</b></div>', '<div class="sub">あいことば <b class="code">${s.code}</b></div><a class="lnsh" href="https://line.me/R/share?text=${encodeURIComponent(shText())}" target="_blank" rel="noopener">LINEで送る</a>')
rep('case"shon":S.share={on:true,id:Math.random().toString(36).slice(2,8),code:String(Math.floor(1000+Math.random()*9000))};toast("共有リンクを作りました");k();document.querySelector(".shc")?.setAttribute("open","");break;',
    'case"shon":shPair();break;')
rep('case"shoff":asPt=false;S.share={on:false};toast("共有をやめました");k();break;',
    'case"shoff":if(!shOffArm){shOffArm=true;el.textContent="もう一度押すと、共有をやめます（相手のスマホとはつながらなくなります）";setTimeout(()=>{shOffArm=false},5000);break}shOffArm=false;asPt=false;shStop();break;')
rep('const t="うちの子手帳のカレンダー https://uchinoko-techo.example/j/"+S.share.id+" あいことば "+S.share.code;',
    'const t=shText();')

# 「共有中」の表示は、パートナーとつないだときだけ（自動保存だけのときは出さない）
s = s.replace('S.share.on', 'shOn()').replace('if(!s.on)return', 'if(!shOn())return')
# ---- 保存と同期 ----
rep('const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(S))}catch(e){}};', open(os.path.join(ROOT, 'tools/sync.js'), encoding='utf-8').read())

# ---- せってい「共有と引き継ぎ」 ----
for g in ['["せってい",[["appset","アイコンと通知","bunny","pink"]', '["せってい",[["baby","赤ちゃんの情報","chick","mint"]']:
    rep(g, g.replace('[["', '[["sync","共有と引き継ぎ","hearthands","mint"],["', 1))
rep('const PAGES={', 'const PAGES={sync:vSync,')
rep('const MSUB={', 'const MSUB={sync:"パートナーと共有・機種変更のときの引き継ぎ",')
rep('const MKW={', 'const MKW={sync:"機種変更 引き継ぎ 共有 パートナー あいことば バックアップ",')
rep('    case"back":', '    case"mvput":mvPut();break;\n    case"mvcopy":{const t=mvFmt(mvCode);try{navigator.clipboard.writeText(t).then(()=>toast("コピーしました"),()=>toast("長押ししてコピーしてください"))}catch(_){toast("長押ししてコピーしてください")}break}\n    case"back":')
rep('  else if(t==="brand"){', '  else if(t==="mvget"){mvGet(v("c"));return}\n  else if(t==="brand"){')

# ---- はじめての画面・あいことば入力 ----
setup = open(os.path.join(ROOT, 'tools/setup.js'), encoding='utf-8').read() + open(os.path.join(ROOT, 'tools/move.js'), encoding='utf-8').read() + open(os.path.join(ROOT, 'tools/icon.js'), encoding='utf-8').read()
tail = 'render(false);\n})();\n</script>'
assert s.rstrip().endswith(tail), s[-200:]
s = s.rstrip()[:-len(tail)] + setup + '\nrender(false);startGate();\n})();\n</script>\n'
rep('/* 下のタブ */', open(os.path.join(ROOT, 'tools/setup.css'), encoding='utf-8').read() + '/* 下のタブ */')

# ---- head（PWA） ----
head = '''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#f7e9ec">
<meta name="description" content="妊娠中から子育て中まで。予定・手続き・家事・買い物をふたりで共有できる、無料の子育て手帳です。">
<script>if(!("standalone" in navigator)){const l=document.createElement("link");l.rel="manifest";l.href="/m/default.webmanifest";document.head.appendChild(l)}</script>
<link rel="icon" href="/icon-192.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="うちの子手帳">
'''
s = s.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', '', 1)
s = head + s.replace('<div class="wrap">', '</head>\n<body>\n<div class="wrap">', 1)
s = s.rstrip() + '\n<script>if("serviceWorker" in navigator)navigator.serviceWorker.register("/sw.js").catch(()=>{})</script>\n</body>\n</html>\n'

os.makedirs(os.path.join(ROOT, 'public'), exist_ok=True)
open(os.path.join(ROOT, 'public/index.html'), 'w', encoding='utf-8').write(s)

# ---- アイコン（赤ちゃんの顔のイラスト） ----
m = re.search(r'"baby_face":\s*"data:image/(\w+);base64,([^"]+)"', s)
if m:
    from PIL import Image
    im = Image.open(io.BytesIO(base64.b64decode(m.group(2)))).convert('RGBA')
    for name, size, pad in [('icon-192.png', 192, .14), ('icon-512.png', 512, .14), ('apple-touch-icon.png', 180, .12), ('icon-maskable.png', 512, .24)]:
        bg = Image.new('RGBA', (size, size), (253, 232, 236, 255))
        inner = int(size * (1 - pad * 2))
        r = inner / max(im.size); f = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
        bg.alpha_composite(f, ((size - f.width) // 2, (size - f.height) // 2))
        bg.convert('RGB').save(os.path.join(ROOT, 'public', name), optimize=True)
else:
    print('baby_face のイラストが見つかりません')
print('ok', len(s))
