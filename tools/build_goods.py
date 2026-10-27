# 話題の育児グッズを、月齢ごとに public/data/goods.json に置く（GitHub Actions で毎月）
#  広告は入れない。いろんなサイトで話題・バズっている物を、話題のもとといっしょに紹介する
#  1. Google ニュース・Bing ニュース・はてなブックマーク・note から見出しを集める
#  2. Gemini（無料枠）に、見出しに出てくる育児グッズを種類ごとにまとめてもらう（作り話はさせない）
#  3. いくつのサイトで話題になっているかを数えて、多い順に並べる
#  4. 買える場所をつける：楽天市場（アフィリエイト）と Yahoo!ショッピング（YAHOO_APP_ID があれば）。
#     レビューの多い人気の商品の中で、いちばん安い新品を、安い順に（中古は入れない）
#  X・Instagram・TikTok は無料では中を読めないので、「SNSで話題」と書いた記事やまとめから拾う
import datetime, html, json, math, os, re, sys, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
from build_events import gem, Limit  # noqa: E402
from build_rank import call, item, APP  # noqa: E402

YAHOO = os.environ.get("YAHOO_APP_ID", "")
USED = re.compile(r"中古|リユース|ジャンク|訳あり|アウトレット|レンタル|USED", re.I)

JST = datetime.timezone(datetime.timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (compatible; uchinoko-techo/1.0)"}
AGES = [
    ("pre", "妊娠中", "妊婦さん・出産準備", ["妊婦 グッズ 話題", "マタニティ グッズ バズ", "出産準備 買ってよかった"]),
    ("m0", "0〜3か月", "新生児〜生後3か月", ["新生児 グッズ 話題", "寝かしつけ グッズ バズ", "新生児 買ってよかった"]),
    ("m4", "4〜6か月", "生後4〜6か月", ["離乳食 グッズ 話題", "赤ちゃん おもちゃ バズ", "生後半年 買ってよかった"]),
    ("m7", "7〜11か月", "生後7〜11か月", ["離乳食 便利グッズ 話題", "ハイハイ 赤ちゃん グッズ", "赤ちゃん グッズ バズ"]),
    ("y1", "1歳", "1歳", ["1歳 おもちゃ 話題", "1歳 グッズ バズ", "1歳 買ってよかった"]),
    ("y2", "2歳", "2歳", ["2歳 おもちゃ 話題", "イヤイヤ期 グッズ", "2歳 買ってよかった"]),
    ("y3", "3歳〜", "3〜5歳", ["3歳 おもちゃ 話題", "幼稚園 グッズ 話題", "4歳 買ってよかった"]),
]
COMMON = ["育児グッズ SNSで話題", "育児グッズ バズった", "子育て グッズ 話題", "育児 神グッズ"]
STAT = {}


def get(url, timeout=60, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    for n in range(3):
        try:
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            print("retry", url[:90], e)
            time.sleep(5 * (n + 1))
    return b""


def clean(x, n):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(x or ""))).strip()[:n]


def host(u):
    try:
        return urllib.parse.urlparse(u).hostname or ""
    except ValueError:
        return ""


def rss(raw):
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        return None


def gnews(q, n=15):
    """Google ニュース（ここ60日）"""
    root = rss(get("https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + " when:60d", "hl": "ja", "gl": "JP", "ceid": "JP:ja"})))
    out = []
    for it in (root.iter("item") if root is not None else []):
        out.append({"t": clean(it.findtext("title"), 140), "s": clean(it.findtext("source"), 40), "d": clean(it.findtext("description"), 160),
                    "l": (it.findtext("link") or "").strip(), "k": "news", "b": 0})
        if len(out) >= n:
            break
    time.sleep(1)
    return out


def bing(q, n=15):
    """Bing ニュース"""
    root = rss(get("https://www.bing.com/news/search?" + urllib.parse.urlencode({"q": q, "format": "rss", "setlang": "ja", "cc": "JP"})))
    out = []
    for it in (root.iter("item") if root is not None else []):
        link = (it.findtext("link") or "").strip()
        real = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("url", [link])[0]
        src = ""
        for ch in it:
            if ch.tag.endswith("Source"):
                src = ch.text or ""
        out.append({"t": clean(it.findtext("title"), 140), "s": clean(src, 40) or host(real), "d": clean(it.findtext("description"), 160),
                    "l": real, "k": "news", "b": 0})
        if len(out) >= n:
            break
    time.sleep(1)
    return out


def hatena(q, n=15):
    """はてなブックマーク（人気順。ブックマーク数＝どれだけ話題か）"""
    root = rss(get("https://b.hatena.ne.jp/search/text?" + urllib.parse.urlencode({"q": q, "mode": "rss", "sort": "popular"})))
    out = []
    if root is None:
        return out
    for it in root.iter():
        if not it.tag.endswith("item"):
            continue
        f = {c.tag.split("}")[-1]: (c.text or "") for c in it}
        link = f.get("link", "").strip()
        try:
            b = int(f.get("bookmarkcount") or 0)
        except ValueError:
            b = 0
        out.append({"t": clean(f.get("title"), 140), "s": host(link), "d": clean(f.get("description"), 160), "l": link, "k": "hatena", "b": b})
        if len(out) >= n:
            break
    time.sleep(1)
    return out


def note(q, n=15):
    """note（スキの数＝どれだけ話題か）"""
    raw = get("https://note.com/api/v3/searches?" + urllib.parse.urlencode({"context": "note", "q": q, "size": n, "sort": "popular"}))
    out = []
    try:
        d = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return out
    notes = (((d.get("data") or {}).get("notes") or {}).get("contents")) or []
    for x in notes[:n]:
        u = (x.get("user") or {}).get("urlname") or ""
        key = x.get("key") or ""
        out.append({"t": clean(x.get("name"), 140), "s": "note", "d": clean(x.get("description") or x.get("body"), 160),
                    "l": f"https://note.com/{u}/n/{key}" if u and key else "", "k": "note", "b": int(x.get("like_count") or 0)})
    time.sleep(1)
    return out


def rakuten_buy(kw):
    try:
        d = call("search", keyword=kw, sort="-reviewCount", hits=15, imageFlag=1)
    except Exception as e:
        print("rakuten", kw, e)
        return None
    xs = [item(x) for x in d.get("Items", [])]
    xs = [x for x in xs if x["p"] and int(x["rc"] or 0) >= 3 and not USED.search(x["n"])][:10]
    if not xs:
        return None
    x = min(xs, key=lambda x: int(x["p"]))
    return {"s": "楽天市場", "n": x["n"], "p": int(x["p"]), "u": x["u"], "img": x["img"], "r": x["r"], "rc": x["rc"]}


def yahoo_buy(kw):
    if not YAHOO:
        return None
    raw = get("https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch?" + urllib.parse.urlencode(
        {"appid": YAHOO, "query": kw, "condition": "new", "sort": "-review_count", "results": 15, "in_stock": "true"}))
    try:
        hits = json.loads(raw or b"{}").get("hits") or []
    except json.JSONDecodeError:
        return None
    xs = []
    for h in hits:
        rv = h.get("review") or {}
        name = re.sub(r"\s+", " ", h.get("name", ""))[:70]
        if h.get("price") and int(rv.get("count") or 0) >= 3 and not USED.search(name) and h.get("condition", "new") == "new":
            img = (h.get("image") or {}).get("medium", "")
            xs.append({"s": "Yahoo!ショッピング", "n": name, "p": int(h["price"]), "u": h.get("url", ""), "img": img, "r": rv.get("rate"), "rc": rv.get("count")})
    xs = xs[:10]
    return min(xs, key=lambda x: x["p"]) if xs else None


def buy(kw):
    out = [b for b in (rakuten_buy(kw) if APP else None, yahoo_buy(kw)) if b]
    time.sleep(1)
    return sorted(out, key=lambda b: b["p"])


SOURCES = [("Googleニュース", gnews), ("Bingニュース", bing), ("はてなブックマーク", hatena), ("note", note)]


def collect(qs):
    heads, seen = [], set()
    for q in qs:
        for name, fn in SOURCES:
            try:
                got = fn(q)
            except Exception as e:
                print("source", name, q, e)
                got = []
            STAT[name] = STAT.get(name, 0) + len(got)
            for h in got:
                key = re.sub(r"\W", "", h["t"])[:40]
                if h["t"] and key not in seen:
                    seen.add(key)
                    heads.append(h)
    return heads


def ask(who, heads):
    lines = [f"[{i}] {h['t']}（{h['s']}）{h['d']}" for i, h in enumerate(heads)]
    prompt = f"""あなたは子育て情報サイトの編集者です。下の見出しは、ニュース・ブログ・はてなブックマーク・note から集めたものです。
この中から、「{who}」の家庭で使う育児グッズのうち、話題になっている物を最大12個あげてください。

きまり:
- 見出しの中に、はっきり出てくる物だけ。出てこない物を作らない。広告・セールのお知らせだけの記事は使わない。
- 「スワドル」「電動バウンサー」のような物の種類で書いてよい（ブランド名が話題ならブランド名も可）。
- 同じ種類の物は1つにまとめ、その物が出てくる見出しの番号を、できるだけ全部 src に入れる。
- why は、どんなところが話題なのかを、ママが読んで分かるやさしい日本語で40字以内。
- kw は、通販サイトでこの物をさがすときの短い言葉（例「スワドル 新生児」）。

JSON だけで答える: {{"items":[{{"name":"…","why":"…","kw":"…","src":["…"]}}]}}

見出し:
{chr(10).join(lines) or "（なし）"}
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
    for x in items:
        raw = x.get("src") or []
        idx = sorted({int(t) for t in (re.sub(r"[^0-9]", "", str(s)) for s in (raw if isinstance(raw, list) else [raw])) if t and int(t) < len(heads)})
        if not idx or not x.get("name"):
            continue
        hs = [heads[i] for i in idx]
        sites = list(dict.fromkeys(h["s"] for h in hs if h["s"]))
        buzz = sum(h["b"] for h in hs)
        ok.append({"t": str(x["name"])[:30], "w": str(x.get("why", ""))[:60], "kw": str(x.get("kw") or x["name"])[:30], "n": len(sites), "f": sites[:4],
                   "a": [{"t": h["t"], "s": h["s"], "l": h["l"]} for h in sorted(hs, key=lambda h: -h["b"]) if h["l"]][:3],
                   "_score": len(sites) + math.log10(1 + buzz)})
    # いくつのサイトで話題か（＋はてブ・noteの数）で多い順
    ok.sort(key=lambda r: -r["_score"])
    for r in ok:
        r.pop("_score")
    return ok[:8], model


def main():
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY がないので、何もしません")
        return
    common = collect(COMMON)
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
        for h in collect(qs) + common:
            if h["t"] not in seen:
                seen.add(h["t"])
                heads.append(h)
        heads = heads[:110]
        print(key, "heads", len(heads), {k: sum(1 for h in heads if h["k"] == k) for k in ("news", "hatena", "note")})
        try:
            rows, model = ask(who, heads)
            if not rows:
                time.sleep(20)
                rows, model = ask(who, heads)
        except Limit:
            print("gemini limit; keep old for", key)
            if key in old:
                out[key] = old[key]
            continue
        for r in rows:
            r["buy"] = buy(r.pop("kw"))
        print(key, model, [(r["t"], r["n"], [(b["s"], b["p"]) for b in r["buy"]]) for r in rows])
        if rows:
            out[key] = rows
        elif key in old:
            out[key] = old[key]
        time.sleep(4)
    print("sources", STAT)
    if not out:
        sys.exit("1つも作れませんでした")
    os.makedirs("public/data", exist_ok=True)
    json.dump({"at": datetime.datetime.now(JST).isoformat(timespec="seconds"), "ages": out},
              open("public/data/goods.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
