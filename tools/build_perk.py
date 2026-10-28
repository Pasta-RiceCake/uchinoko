# 「もらえる特典・お店の教室」を、各お店の公式ページと毎月見くらべて直す
#  - ページの文がかわったとき（と、はじめての実行）だけ Gemini に見くらべてもらう
#  - 終わった特典は「ended」にしてかくす。元のページにない金額が出てきた書きかえは使わない
#  - 出力は public/data/perk.json。失敗したときは前の内容をそのまま残す
import datetime, hashlib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_events import JST, KEY, Limit, decode, fetch, gem, text_of  # noqa: E402
from build_tax import nums, norm  # noqa: E402

OUT = "public/data/perk.json"
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "perk_base.json")
FORCE = os.environ.get("PERK_FORCE", "") == "1"
FIELDS = {"ev": ["title", "desc", "how"], "gift": ["title", "what", "how", "who"]}

ASK = """あなたは、プレママ向けサイトの「お店の特典・教室」の紹介文を、お店の公式ページとくらべて直す係です。

- 公式ページとくいちがう中身・条件・もらえる物・申しこみ方があれば、その項目だけ直してください。
- 合っている項目は、一字も変えずにそのまま返してください。
- 公式ページで、この特典・教室が終わった（受付終了・配布終了・サービス終了）とはっきり書いてあれば "ended": true。はっきりしないときは false。
- 公式ページの文をそのまま写さず、やさしい日本語で短く。公式ページにない金額・日付は書かないでください。

JSONだけで答えてください: {{"changed": true か false, "ended": true か false, "item": {{...同じ項目名で...}}, "why": "何を直したか（直さなかったら空）"}}

# いまの紹介文
{cur}

# 公式ページ（{url}）
{src}
"""


def check(kind, cur, text):
    keep = {k: cur[k] for k in FIELDS[kind]}
    out, model = gem([{"text": ASK.format(cur=json.dumps({"shop": cur["shop"], **keep}, ensure_ascii=False, indent=1), url=cur["url"], src=text)}])
    m = re.search(r"\{.*\}", out or "", re.S)
    if not m:
        return None
    try:
        r = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if r.get("ended"):
        print("  ended:", r.get("why", "")[:200])
        return {**cur, "ended": True, "why": r.get("why", "")}
    if not r.get("changed"):
        print("  ok", model)
        return cur
    it = r.get("item") or {}
    new = {k: it.get(k) if isinstance(it.get(k), str) and it.get(k).strip() else cur[k] for k in FIELDS[kind]}
    added = nums(" ".join(new.values())) - nums(" ".join(keep.values()))
    bad = [x for x in added if x not in nums(text)]
    if bad:
        print("  numbers not in page, skip:", bad)
        return None
    print("  updated:", r.get("why", "")[:200])
    return {**cur, **new, "why": r.get("why", "")}


def main():
    today = datetime.datetime.now(JST).date().isoformat()
    base = json.load(open(BASE))
    try:
        old = json.load(open(OUT))
    except Exception:
        old = {}
    hashes, ok_all, res = dict(old.get("hash", {})), True, {}
    cache = {}
    for kind in ("ev", "gift"):
        prev = {(x["shop"], x["title0"]): x for x in old.get(kind, []) if "title0" in x}
        res[kind] = []
        for b in base[kind]:
            key = (b["shop"], b["title"])
            cur = {**b, **{k: v for k, v in prev.get(key, {}).items() if k in FIELDS[kind] or k in ("ended", "why", "upd")}, "title0": b["title"]}
            u = b["url"]
            try:
                if u not in cache:
                    fu, ct, raw = fetch(u)
                    cache[u] = text_of(decode(raw, ct))[:9000]
                text = cache[u]
            except Exception as e:
                print(b["shop"], b["title"], "fetch fail", str(e)[:80])
                ok_all = False
                res[kind].append(cur)
                continue
            h = hashlib.sha1((norm(text) + json.dumps(b, ensure_ascii=False)).encode()).hexdigest()
            hk = kind + "|" + b["shop"] + "|" + b["title"]
            print(b["shop"], b["title"], "changed" if hashes.get(hk) != h else "same")
            if (FORCE or hashes.get(hk) != h) and KEY:
                try:
                    r = check(kind, cur, text)
                except Limit:
                    print("  gemini limit, keep")
                    r = None
                if r is None:
                    ok_all = False
                    hashes.pop(hk, None)
                else:
                    if r is not cur:
                        r["upd"] = today
                    cur = r
                    hashes[hk] = h
            elif hashes.get(hk) != h:
                ok_all = False
            res[kind].append(cur)
    json.dump({"checked": today if ok_all else old.get("checked", ""), **res, "hash": hashes}, open(OUT, "w"), ensure_ascii=False, indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
