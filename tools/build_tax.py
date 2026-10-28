# 「お金の見通し」の「税金・扶養のこと」を、国税庁・厚生労働省などのページと毎月見くらべて直す
#  - 元のページの文がかわったとき（と、はじめての実行）だけ Gemini に見くらべてもらう
#  - 書きかえた文に、元のページにない金額が出てきたら使わない（まちがいを入れないため）
#  - 出力は public/data/tax.json。失敗したときは前の内容をそのまま残す
import datetime, hashlib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_events import JST, KEY, Limit, decode, fetch, gem, text_of  # noqa: E402

OUT = "public/data/tax.json"
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tax_base.json")
NTA = "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/"
SRC = {
    "医療費控除（確定申告で税金が戻る）": [["国税庁 医療費控除", NTA + "1120.htm"], ["国税庁 出産費用", NTA + "1124.htm"]],
    "赤ちゃんの健康保険（だれの扶養に入れる？）": [["協会けんぽ 被扶養者とは", "https://www.kyoukaikenpo.or.jp/g7/cat710/sb3160/sbb3163/1959-230/"],
                                         ["厚生労働省 夫婦共同扶養", "https://www.mhlw.go.jp/web/t_doc?dataId=00tc5892&dataType=1&pageNo=1"]],
    "税金の扶養（年末調整）": [["国税庁 扶養控除", NTA + "1180.htm"]],
    "育休の年は、パートナーの年末調整で「配偶者控除」": [["国税庁 配偶者控除", NTA + "1191.htm"], ["国税庁 配偶者特別控除", NTA + "1195.htm"]],
    "帝王切開や入院が長くなったとき（高額療養費）": [["厚生労働省 高額療養費", "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryouhoken/juuyou/kougakuiryou/index.html"]],
}
FORCE = os.environ.get("TAX_FORCE", "") == "1"


def norm(s):
    s = s.translate(str.maketrans("０１２３４５６７８９，．", "0123456789,."))
    return re.sub(r"\s+", "", s)


def nums(s):
    # 「136万円」「1,000万円」「5％」「200万円」など、金額・割合だけを取り出す
    return set(x.replace(",", "") for x in re.findall(r"\d[\d,]*(?:\.\d+)?(?:万円|円|％|%)", norm(s)))


def page_text(u):
    fu, ct, b = fetch(u)
    t = text_of(decode(b, ct))
    i = max(t.find("概要"), t.find("対象"), 0)
    return t[max(i - 200, 0):][:9000]


ASK = """あなたは、ママ・プレママ向けサイトの文を、公式ページとくらべて直す係です。
下の「いまの文」を「公式ページ」とくらべてください。

- 公式ページとくいちがう金額・年・条件、古くなった制度があれば、その文だけ直してください。
- 合っている文は、一字も変えずにそのまま返してください。
- 新しい制度の変更が公式ページにあり、ママに大事なら、短い文を1つ足してもかまいません。
- 文体は、いまの文と同じ、やさしい日本語。公式ページの文をそのまま写さず、ママが読んですぐわかる言葉に言いかえてください（「被扶養者」→「扶養」、「生計を維持する」→「家計を主に支える」など）。1つの文は短く。<b>見出し</b>の形はそのまま。
- 公式ページに書いていない金額は書かないでください。わからないことは書かないでください。
- 「いつ」の欄（when）も同じように。

JSONだけで答えてください: {{"changed": true か false, "when": "...", "points": ["...", ...], "why": "何を直したか（直さなかったら空）"}}

# いまの文
{cur}

# 公式ページ
{src}
"""


def check(item, texts):
    cur = json.dumps({"title": item["title"], "when": item["when"], "points": item["points"]}, ensure_ascii=False, indent=1)
    src = "\n\n".join(f"## {n}\n{t}" for n, t in texts)
    out, model = gem([{"text": ASK.format(cur=cur, src=src)}])
    m = re.search(r"\{.*\}", out or "", re.S)
    if not m:
        print("  no answer")
        return None
    try:
        r = json.loads(m.group(0))
    except json.JSONDecodeError:
        print("  bad json")
        return None
    if not r.get("changed"):
        print("  ok (no change)", model)
        return item
    ps = [p for p in r.get("points", []) if isinstance(p, str) and p.strip()]
    if len(ps) < len(item["points"]) - 1:
        print("  too short, skip")
        return None
    official = nums(src)
    new = nums(" ".join(ps) + r.get("when", "")) - nums(" ".join(item["points"]) + item["when"])
    bad = [x for x in new if x not in official]
    if bad:
        print("  numbers not in official page, skip:", bad)
        return None
    print("  updated:", r.get("why", "")[:200])
    return {**item, "when": r.get("when") or item["when"], "points": ps, "why": r.get("why", "")}


def main():
    today = datetime.datetime.now(JST).date().isoformat()
    base = json.load(open(BASE))
    try:
        old = json.load(open(OUT))
    except Exception:
        old = {"items": {}, "hash": {}}
    items, hashes = {}, dict(old.get("hash", {}))
    ok_all = True
    for b in base:
        t = b["title"]
        prev = old["items"].get(t) or {}
        cur = {"title": t, "when": prev.get("when", b["when"]), "points": prev.get("points", b["points"])}
        texts, changed = [], FORCE
        for n, u in SRC.get(t, []):
            try:
                x = page_text(u)
            except Exception as e:
                print("  fetch fail", u, str(e)[:80])
                continue
            h = hashlib.sha1(norm(x).encode()).hexdigest()
            if hashes.get(u) != h:
                changed = True
            hashes[u] = h
            texts.append((n, x))
        print(t, "changed" if changed else "same")
        if len(texts) < len(SRC.get(t, [])):
            ok_all = False
        res = cur
        if changed and texts and KEY:
            try:
                r = check(cur, texts)
            except Limit:
                print("  gemini limit, keep")
                r = None
                for n, u in SRC.get(t, []):
                    hashes.pop(u, None)  # 次回もう一度
            if r is None:
                ok_all = False
                for n, u in SRC.get(t, []):
                    hashes.pop(u, None)
            else:
                res = r
                if r is not cur:
                    res["upd"] = today
        elif changed:
            ok_all = False
            for n, u in SRC.get(t, []):
                hashes.pop(u, None)
        items[t] = {"when": res["when"], "points": res["points"], "src": SRC.get(t, []),
                    **({"upd": res.get("upd") or prev.get("upd")} if (res.get("upd") or prev.get("upd")) else {}),
                    **({"why": res.get("why") or prev.get("why")} if (res.get("why") or prev.get("why")) else {})}
    json.dump({"checked": today if ok_all else old.get("checked", ""), "items": items, "hash": hashes}, open(OUT, "w"), ensure_ascii=False, indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
