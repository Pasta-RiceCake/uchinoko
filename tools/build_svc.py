# 家族のいる市区町村の「使えるサービス」の市ごとの違いを、市の公式サイトから読んで public/data/svc/ に置く
#  - 国の基本（児童手当・医療費助成・産後ケア…）に、その市の年齢・金額・申しこみ先を足す
#  - 出産祝い金・おむつ券など、その市だけのサービスも拾う
#  - 1回の実行で MAX_CITIES 市まで。古い市から順に、90日たったら読み直す
import datetime, json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_events import KEY, SITE, JST, Limit, base_domain, decode, fetch, gem, get_json, host, links, text_of  # noqa: E402

OUT = "public/data/svc"
MAX_CITIES = int(os.environ.get("MAX_CITIES", "15"))
ONLY = os.environ.get("CITY", "")
KEYS = {
    "teate": "児童手当",
    "iryo": "子どもの医療費助成",
    "ninpu": "妊婦のための支援給付（出産・子育て応援）",
    "sango": "産後ケア",
    "ichiji": "一時預かり",
    "famisapo": "ファミリー・サポート・センター",
    "daredemo": "こども誰でも通園制度",
    "center": "子育て支援センター・児童館",
}
WORDS = ["子育て", "子ども", "こども", "妊娠", "出産", "乳幼児", "赤ちゃん", "手当", "助成", "給付", "医療費", "医療証", "産後ケア", "一時預かり",
         "ファミリー・サポート", "ファミサポ", "誰でも通園", "支援センター", "児童館", "祝い金", "お祝い", "おむつ", "応援", "子育て支援", "補助", "クーポン", "タクシー"]
STRONG = ["産後ケア", "医療費助成", "子ども医療", "こども医療", "乳幼児医療", "児童手当", "一時預かり", "ファミリー・サポート", "誰でも通園", "祝い金", "おむつ", "出産応援", "子育て応援", "妊婦支援"]


def score(t):
    return sum(3 for w in STRONG if w in t) + sum(1 for w in WORDS if w in t)


def crawl(site, max_pages=90):
    if not site:
        return []
    root = base_domain(host(site))
    seen, queue, pages = set(), [(site, "トップ", 0, 99)], []
    while queue and len(seen) < max_pages:
        queue.sort(key=lambda x: -x[3])
        u, label, depth, _ = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        try:
            fu, ct, b = fetch(u)
        except Exception as e:
            print("  skip", u[:90], str(e)[:60])
            continue
        if "html" not in ct:
            continue
        html = decode(b, ct)
        t = text_of(html)
        sc = score(label + " " + t[:6000])
        if depth > 0 and sc >= 8:
            pages.append({"u": fu, "text": t[:7000], "label": label, "sc": sc})
        if depth >= 3:
            continue
        for lu, lt in links(html, fu):
            if not host(lu).endswith(root) or lu in seen or re.search(r"\.(jpg|png|gif|zip|xlsx?|docx?|pdf)$", lu, re.I):
                continue
            ls = score(lt)
            if ls >= 1 or (depth == 0 and "kosodate" in lu):
                queue.append((lu, lt, depth + 1, ls - depth))
        time.sleep(0.5)
    pages.sort(key=lambda p: -p["sc"])
    return pages[:14]


def ask(city, site):
    pages = crawl(site)
    print(" ", city, "pages", [(p["sc"], p["label"][:20]) for p in pages])
    if not pages:
        return None, ""
    srcs = [p["u"] for p in pages]
    docs = "".join(f"\n--- 資料 URL: {p['u']} 見出し: {p['label']} ---\n{p['text']}" for p in pages)
    names = "\n".join(f'- {k}: {v}' for k, v in KEYS.items())
    prompt = f"""下の資料は、{city}の公式サイト（{site}）から集めたものです。
子育て中の家族や妊婦さんに向けて、{city}のサービスの内容を、資料に書いてあることだけで短くまとめてください。

1. 次のサービスについて、{city}ならではの中身（対象の年齢、自己負担、金額、回数、申しこみ先など）を、やさしい日本語で80字以内にまとめる。
   資料に書いていないサービスは入れない。国の決まりと同じことしか書いていない場合も入れない。
{names}
2. 上にない、{city}だけの子育てサービス（出産祝い金、おむつ・ミルクの券や配達、タクシー券、子育てアプリのポイント、紙おむつ用ごみ袋など）を最大6つ。
   赤ちゃん〜未就学児の家族か妊婦さんが使える物だけ。大人だけ・小学生以上だけの物は入れない。
3. url には、その中身がのっていた資料のURLをそのまま入れる。

答えはJSONだけ。形:
{{"svc":{{"iryo":{{"t":"…","url":"…"}}}},"extra":[{{"n":"サービスの名前","tag":"もらえる/預けたい/休みたい/遊びに行く/その他 のどれか","t":"どんな物か80字以内","how":"申しこみ方40字以内","url":"…"}}]}}
{docs}"""
    text, model = gem([{"text": prompt}])
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None, model
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None, model
    ok = lambda u: u if u in srcs else ""
    svc = {}
    for k, v in (d.get("svc") or {}).items():
        if k in KEYS and isinstance(v, dict) and str(v.get("t", "")).strip():
            svc[k] = {"t": str(v["t"]).strip()[:120], "u": ok(str(v.get("url", "")).strip())}
    extra = []
    for x in (d.get("extra") or [])[:6]:
        if isinstance(x, dict) and str(x.get("n", "")).strip() and str(x.get("t", "")).strip():
            extra.append({"n": str(x["n"]).strip()[:40], "tag": str(x.get("tag", "その他"))[:8], "t": str(x["t"]).strip()[:120],
                          "how": str(x.get("how", "")).strip()[:60], "u": ok(str(x.get("url", "")).strip())})
    return {"s": svc, "x": extra}, model


SEED = ["北海道札幌市", "宮城県仙台市", "埼玉県さいたま市", "千葉県千葉市", "神奈川県横浜市", "神奈川県川崎市", "神奈川県相模原市", "新潟県新潟市",
        "静岡県静岡市", "静岡県浜松市", "愛知県名古屋市", "京都府京都市", "大阪府大阪市", "大阪府堺市", "兵庫県神戸市", "岡山県岡山市", "広島県広島市",
        "福岡県北九州市", "福岡県福岡市", "熊本県熊本市"] + ["東京都" + x for x in "世田谷区 練馬区 大田区 江戸川区 足立区 杉並区 板橋区 江東区 葛飾区 品川区 北区 新宿区 中野区 豊島区 目黒区 墨田区 港区 渋谷区 文京区 荒川区 台東区 中央区 千代田区".split()]


def main():
    if not KEY:
        print("GEMINI_API_KEY がまだ入っていないので、何もしません")
        return
    cities = json.load(open("public/data/cities.json", encoding="utf-8"))
    want = [ONLY] if ONLY else get_json(SITE + "/api/cities").get("cities", [])
    fam = set(want)
    if not ONLY:
        # 家族のいる市のあとに、検索用のページを作る大きな市も少しずつ読む
        want = want + [x for x in SEED if x not in fam]
    today = datetime.datetime.now(JST)
    todo = []
    for name in want:
        c = cities.get(name)
        if not c:
            print("市区町村が見つからない", name)
            continue
        p = os.path.join(OUT, c["c"] + ".json")
        age = 999
        if os.path.exists(p):
            age = (today - datetime.datetime.fromisoformat(json.load(open(p, encoding="utf-8"))["at"])).days
        if ONLY or age >= 90:
            todo.append((age, name, c, p))
    todo.sort(key=lambda x: (x[1] not in fam, -x[0]))
    print("読む市区町村", len(todo), "のうち", min(len(todo), MAX_CITIES))
    os.makedirs(OUT, exist_ok=True)
    for age, name, c, p in todo[:MAX_CITIES]:
        try:
            d, model = ask(name, c.get("u", ""))
        except Limit:
            print("無料の上限に来たので、今日はここまで")
            break
        except Exception as e:
            print("error", name, e)
            continue
        if not d:
            print(name, "読めませんでした")
            continue
        print(name, model, "svc", list(d["s"]), "extra", [x["n"] for x in d["x"]])
        json.dump({"at": today.isoformat(timespec="seconds"), "city": name, "site": c.get("u", ""), **d},
                  open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        time.sleep(8)


if __name__ == "__main__":
    main()
