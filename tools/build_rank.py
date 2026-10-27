# 楽天市場の売れ筋ランキングを public/data/rank.json に置く（GitHub Actions で週1回）
#  リンクは楽天アフィリエイトの報酬つき（affiliateId）。PR表示はサイト側で出す
import datetime, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

APP = os.environ.get("RAKUTEN_APP_ID", "")
ACC = os.environ.get("RAKUTEN_ACCESS_KEY", "")
AFF = "58e1dcc5.ffbb96dd.58e1dcc6.c118f976"
ORIGIN = "https://uchinoko.pocket-app.workers.dev"
BABY = 100533  # キッズ・ベビー・マタニティ
TOY = 566382   # おもちゃ
# 新しいAPIのURLがうまくいかないときは、古いURLも試す
BASES = {
    "rank": ["https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601", "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20220601"],
    "genre": ["https://openapi.rakuten.co.jp/ichibagt/api/IchibaGenre/Search/20260701", "https://app.rakuten.co.jp/services/api/IchibaGenre/Search/20140222"],
    "search": ["https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601", "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"],
}
good = {}


def call(kind, **q):
    q.update({"applicationId": APP, "affiliateId": AFF, "format": "json", "formatVersion": 2})
    if ACC:
        q["accessKey"] = ACC
    urls = [good[kind]] if kind in good else BASES[kind]
    last = None
    for base in urls:
        req = urllib.request.Request(base + "?" + urllib.parse.urlencode(q), headers={"Origin": ORIGIN, "Referer": ORIGIN + "/", "User-Agent": "uchinoko-techo/1.0"})
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=60).read())
            good[kind] = base
            time.sleep(1.2)
            return d
        except urllib.error.HTTPError as e:
            last = f"{e.code} {e.read()[:300]}"
            print("  ng", base, last)
    raise RuntimeError(last)


def children(gid):
    d = call("genre", genreId=gid)
    ch = d.get("children", [])
    ch = [c.get("child", c) for c in ch]
    if ch:
        print("  raw child", json.dumps(ch[0], ensure_ascii=False)[:300])
    def nm(c):
        for k in ("genreName", "name", "genreNameJa", "nameJa"):
            if c.get(k):
                return c[k]
        for v in c.values():
            if isinstance(v, dict):
                n = nm(v)
                if n:
                    return n
        return ""
    def gid(c):
        return c.get("genreId") or next((v.get("genreId") for v in c.values() if isinstance(v, dict) and v.get("genreId")), None)
    return [(gid(c), nm(c)) for c in ch]


# API の affiliateUrl には自分のIDが入らないことがあるので、自分のIDのリンクを作る
def aff(u):
    if not u:
        return ""
    if "hb.afl.rakuten.co.jp" in u:
        pc = urllib.parse.parse_qs(urllib.parse.urlparse(u).query).get("pc")
        if pc:
            u = pc[0]
    u = u.split("?")[0] if "item.rakuten.co.jp" in u else u
    q = urllib.parse.quote(u, safe="")
    return f"https://hb.afl.rakuten.co.jp/ichiba/{AFF}/?pc={q}&m={q}"


def item(x):
    img = (x.get("mediumImageUrls") or [""])[0]
    img = img.get("imageUrl", "") if isinstance(img, dict) else img
    return {"n": re.sub(r"\s+", " ", x.get("itemName", ""))[:70], "p": x.get("itemPrice"), "img": img.split("?")[0] + "?_ex=128x128" if img else "",
            "u": aff(x.get("itemUrl") or ""), "s": x.get("shopName", ""), "r": x.get("reviewAverage"), "rc": x.get("reviewCount")}


def rank(gid, n=10):
    d = call("rank", genreId=gid)
    return [item(x) for x in d.get("Items", [])[:n]]


def main():
    if not APP:
        print("RAKUTEN_APP_ID がまだ入っていないので、何もしません")
        return
    try:
        kids = children(BABY)
    except Exception as e:
        print("genre error", e)
        kids = []
    print("baby genres", kids)
    try:
        toys = children(TOY)
    except Exception as e:
        print("genre error", e)
        toys = []
    print("toy genres", toys)

    def find(lst, *words):
        for gid, name in lst:
            if name and any(w in name for w in words):
                return gid
        return None

    tabs = {
        "ベビー用品": BABY,
        "マタニティ": find(kids, "マタニティ"),
        "授乳グッズ": find(kids, "授乳", "食事"),
        "おでかけ": find(kids, "ベビーカー", "おでかけ", "外出"),
        "ベビー服": find(kids, "ベビー服", "ベビーファッション"),
        "出産準備": find(kids, "寝具", "ベッド", "ねんね"),
        "おもちゃ・知育": find(toys, "ベビー", "知育") or TOY,
    }
    out = {}
    for name, gid in tabs.items():
        if not gid:
            print("genre not found", name)
            continue
        try:
            out[name] = rank(gid)
            print(name, gid, len(out[name]), out[name][0]["n"] if out[name] else "")
        except Exception as e:
            print("error", name, e)
    try:
        d = call("search", keyword="出産内祝い", sort="-reviewCount", hits=10)
        out["内祝い"] = [item(x) for x in d.get("Items", [])[:10]]
        print("内祝い", len(out["内祝い"]))
    except Exception as e:
        print("error 内祝い", e)
    if not out:
        sys.exit("ランキングが1つも取れませんでした")
    os.makedirs("public/data", exist_ok=True)
    json.dump({"at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds"), "tabs": out},
              open("public/data/rank.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
