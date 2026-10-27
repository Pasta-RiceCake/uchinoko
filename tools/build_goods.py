# 話題の育児グッズを、月齢ごとに public/data/goods.json に置く（GitHub Actions で毎月）
#  1. ネットのニュース・記事の見出し（Google ニュース）と、楽天のランキング・レビューの多い商品を集める
#  2. Gemini（無料枠）に「いま話題になっている物」を月齢ごとに選んでもらう（集めた中から選ぶだけ。作り話はさせない）
#  3. 楽天で同じ物をさがして、写真・値段・自分のアフィリエイトIDのリンクをつける
import datetime, html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
from build_events import gem, Limit  # noqa: E402
from build_rank import call, item, APP  # noqa: E402

JST = datetime.timezone(datetime.timedelta(hours=9))
UA = {"User-Agent": "uchinoko-techo/1.0"}
AGES = [
    ("pre", "妊娠中", "妊婦さん・出産準備", ["妊婦 便利グッズ 話題", "マタニティ グッズ 人気", "出産準備 買ってよかった"]),
    ("m0", "0〜3か月", "新生児〜生後3か月", ["新生児 便利グッズ 話題", "育児グッズ 買ってよかった 新生児", "寝かしつけ グッズ 話題"]),
    ("m4", "4〜6か月", "生後4〜6か月", ["生後半年 おもちゃ 人気", "離乳食 グッズ 話題", "ベビー 便利グッズ SNS 話題"]),
    ("m7", "7〜11か月", "生後7〜11か月", ["ハイハイ 赤ちゃん おもちゃ 人気", "離乳食 便利グッズ 人気", "ベビー グッズ 話題 2026"]),
    ("y1", "1歳", "1歳", ["1歳 おもちゃ 人気", "1歳 誕生日プレゼント 話題", "1歳 便利グッズ"]),
    ("y2", "2歳", "2歳", ["2歳 おもちゃ 人気", "2歳 知育 話題", "イヤイヤ期 グッズ"]),
    ("y3", "3歳〜", "3〜5歳", ["3歳 おもちゃ 人気", "幼稚園 グッズ 話題", "知育玩具 人気 2026"]),
]
COMMON = ["育児グッズ 話題", "ベビー用品 新商品", "子育て 便利グッズ SNSで話題"]


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    for n in range(3):
        try:
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            print("retry", url[:90], e)
            time.sleep(5 * (n + 1))
    return b""


def news(q, n=15):
    """Google ニュースの見出し（ここ60日）"""
    u = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + " when:60d", "hl": "ja", "gl": "JP", "ceid": "JP:ja"})
    raw = get(u)
    out = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return out
    for it in root.iter("item"):
        t = html.unescape(it.findtext("title") or "")
        src = it.findtext("source") or ""
        d = re.sub(r"<[^>]+>", " ", html.unescape(it.findtext("description") or ""))
        out.append({"t": t[:140], "s": src[:40], "d": re.sub(r"\s+", " ", d)[:200]})
        if len(out) >= n:
            break
    time.sleep(1)
    return out


def rakuten_hot(keyword, n=10):
    """レビューが多い順（＝よく買われて話題の物）"""
    try:
        d = call("search", keyword=keyword, sort="-reviewCount", hits=n)
        return [item(x) for x in d.get("Items", [])[:n]]
    except Exception as e:
        print("rakuten", keyword, e)
        return []


def find(keyword):
    try:
        d = call("search", keyword=keyword, sort="-reviewCount", hits=5, imageFlag=1)
    except Exception as e:
        print("find", keyword, e)
        return None
    for x in d.get("Items", []):
        it = item(x)
        if it["img"]:
            return it
    return None


def ask(label, who, heads, hot):
    lines = [f"[{i}] {h['t']}（{h['s']}）{h['d']}" for i, h in enumerate(heads)]
    rk = [f"[R{i}] {x['n']}（レビュー{x['rc']}件）" for i, x in enumerate(hot)]
    prompt = f"""あなたは子育て情報サイトの編集者です。下の「ネットの記事の見出し」と「楽天でよく買われている商品」だけを見て、
いま「{who}」の家庭で話題になっている育児グッズを最大8つ選んでください。

きまり:
- 見出しか商品の中に、はっきり出てくる物だけを選ぶ。出てこない物を作らない。
- 1つの商品名ではなく「スワドル」「電動バウンサー」のような、物の種類で書いてよい（ブランド名が話題ならブランド名も可）。
- 同じ種類の物は1つにまとめる。
- why は、ママが読んで分かるやさしい日本語で40字以内。「話題」「バズ」などの言葉を使いすぎない。
- src には、根拠にした見出しや商品の番号（例 "3", "R2"）を入れる。
- kw は、楽天で検索するときの言葉（短く）。

JSON だけで答える: {{"items":[{{"name":"…","why":"…","kw":"…","src":["…"]}}]}}

ネットの記事の見出し:
{chr(10).join(lines) or "（なし）"}

楽天でよく買われている商品:
{chr(10).join(rk) or "（なし）"}
"""
    text, model = gem([{"text": prompt}])
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return [], model
    try:
        items = json.loads(m.group(0)).get("items", [])
    except json.JSONDecodeError:
        return [], model
    ok = []
    valid = {str(i) for i in range(len(heads))} | {f"R{i}" for i in range(len(hot))}
    for x in items:
        raw = x.get("src") or []
        src = [t for t in (re.sub(r"[^0-9R]", "", str(s).upper()) for s in (raw if isinstance(raw, list) else [raw])) if t in valid]
        if not src or not x.get("name"):
            continue
        ok.append({"name": str(x["name"])[:30], "why": str(x.get("why", ""))[:60], "kw": str(x.get("kw") or x["name"])[:30],
                   "from": sorted({heads[int(s)]["s"] for s in src if not s.startswith("R") and heads[int(s)]["s"]} | ({"楽天のレビュー"} if any(s.startswith("R") for s in src) else set()))[:3]})
    return ok[:8], model


def main():
    if not os.environ.get("GEMINI_API_KEY") or not APP:
        print("GEMINI_API_KEY か RAKUTEN_APP_ID がないので、何もしません")
        return
    common = [h for q in COMMON for h in news(q, 10)]
    old = {}
    try:
        old = json.load(open("public/data/goods.json", encoding="utf-8")).get("ages", {})
    except Exception:
        pass
    out = {}
    only = [k for k in os.environ.get("GOODS_ONLY", "").split(",") if k]
    for key, label, who, qs in AGES:
        if only and key not in only:
            if key in old:
                out[key] = old[key]
            continue
        heads, seen = [], set()
        for h in [x for q in qs for x in news(q)] + common:
            if h["t"] not in seen:
                seen.add(h["t"])
                heads.append(h)
        heads = heads[:45]
        hot = rakuten_hot(qs[0].replace(" 話題", "").replace(" SNS", ""), 10)
        print(key, "news", len(heads), "rakuten", len(hot))
        try:
            picks, model = ask(label, who, heads, hot)
            if not picks:
                time.sleep(20)
                picks, model = ask(label, who, heads, hot)
        except Limit:
            print("gemini limit; keep old for", key)
            if key in old:
                out[key] = old[key]
            continue
        rows = []
        for p in picks:
            it = find(p["kw"])
            if not it:
                continue
            rows.append({"t": p["name"], "w": p["why"], "f": p["from"], "n": it["n"], "img": it["img"], "p": it["p"], "u": it["u"], "r": it["r"], "rc": it["rc"]})
        print(key, model, [r["t"] for r in rows])
        if rows:
            out[key] = rows
        elif key in old:
            out[key] = old[key]
        time.sleep(4)
    if not out:
        sys.exit("1つも作れませんでした")
    os.makedirs("public/data", exist_ok=True)
    json.dump({"at": datetime.datetime.now(JST).isoformat(timespec="seconds"), "ages": out},
              open("public/data/goods.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
