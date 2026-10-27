# 家族のいる市区町村の子育てイベントを、Gemini（無料枠）に公式サイトから探してもらい public/data/events/ に置く
#  - 1回の実行で MAX_CITIES 市まで。古い市から順に、25日たったら読み直す
#  - 無料の上限に来たら（429）、そこで止めて、作れた分だけ保存する
import datetime, json, os, re, sys, time, urllib.parse, urllib.request

OUT = "public/data/events"
SITE = os.environ.get("SITE", "https://uchinoko.pocket-app.workers.dev")
KEY = os.environ.get("GEMINI_API_KEY", "")
MODELS = [m for m in os.environ.get("GEMINI_MODEL", "gemini-flash-latest,gemini-flash-lite-latest").split(",") if m]
MAX_CITIES = int(os.environ.get("MAX_CITIES", "40"))
ONLY = os.environ.get("CITY", "")
JST = datetime.timezone(datetime.timedelta(hours=9))
UA = {"User-Agent": "uchinoko-techo/1.0"}
KINDS = ["支援センター・児童館", "親子教室", "離乳食・健康", "両親学級・妊婦", "おでかけ・その他"]


class Limit(Exception):
    pass


def get_json(url, body=None, timeout=240):
    data = json.dumps(body).encode() if body is not None else None
    h = dict(UA)
    if data:
        h["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise Limit(e.read()[:300])
        raise RuntimeError(f"{e.code} {e.read()[:300]}")


def host(u):
    try:
        return urllib.parse.urlparse(u).hostname or ""
    except ValueError:
        return ""


def base_domain(h):
    p = h.split(".")
    return ".".join(p[-3:]) if h.endswith((".lg.jp", ".or.jp", ".ne.jp", ".co.jp", ".ac.jp", ".go.jp")) else ".".join(p[-2:])


def ask(city, site, today):
    m1 = today.strftime("%Y年%-m月")
    nx = (today.replace(day=1) + datetime.timedelta(days=32))
    m2 = nx.strftime("%Y年%-m月")
    prompt = f"""あなたは子育て中の家族のために、{city}の公式情報を調べるアシスタントです。
{city}（公式サイト {site or "不明"}）が出している、{m1}と{m2}に開かれる赤ちゃん・乳幼児・妊婦さん向けの催しを、Google検索で探してください。
対象: 子育て支援センターや児童館の催し、親子教室・赤ちゃん教室、離乳食教室、育児相談・身体測定、両親学級・母親学級・プレママ教室、図書館のおはなし会など。
市の公式サイトか、市の施設（支援センター・児童館・保健センター・図書館など）の公式ページにのっているものだけにしてください。のっていないものを作らないでください。
答えはJSONだけで、ほかの文は書かないでください。形:
{{"events":[{{"date":"YYYY-MM-DD","time":"10:00〜11:30","title":"催しの名前","place":"場所","target":"対象（例：0歳児と保護者）","kind":"{"・".join(KINDS)} のどれか","need":"予約がいるか・持ち物など短く","url":"のっていたページのURL"}}]}}
毎週・毎月ある催しは、それぞれの日を1件ずつにしてください。最大60件。見つからなければ {{"events":[]}}。"""
    last = None
    for model in MODELS:
        try:
            r = get_json(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={KEY}",
                {"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}], "generationConfig": {"temperature": 0.1}},
            )
        except Limit as e:
            last = e
            print("limit", model, e)
            continue
        cand = (r.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
        srcs = [c.get("web", {}).get("uri", "") for c in cand.get("groundingMetadata", {}).get("groundingChunks", [])]
        return text, srcs, model
    raise last or RuntimeError("no model")


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0)).get("events", [])
    except json.JSONDecodeError:
        return []


def clean(evs, site, today):
    lo, hi = today.date(), (today + datetime.timedelta(days=75)).date()
    ok_dom = base_domain(host(site)) if site else ""
    out, seen = [], set()
    for e in evs:
        try:
            d = datetime.date.fromisoformat(str(e.get("date", ""))[:10])
        except ValueError:
            continue
        if not lo <= d <= hi:
            continue
        t = str(e.get("title", "")).strip()[:60]
        u = str(e.get("url", "")).strip()
        if not t:
            continue
        h = host(u)
        # 市の公式サイトか自治体のドメインのページだけ
        if u and not (h.endswith(".lg.jp") or (ok_dom and h.endswith(ok_dom))):
            u = ""
        k = (d, t)
        if k in seen:
            continue
        seen.add(k)
        kind = e.get("kind") if e.get("kind") in KINDS else "おでかけ・その他"
        out.append({"d": d.isoformat(), "tm": str(e.get("time", ""))[:30], "t": t, "pl": str(e.get("place", ""))[:60],
                    "to": str(e.get("target", ""))[:40], "k": kind, "n": str(e.get("need", ""))[:80], "u": u})
    out.sort(key=lambda x: (x["d"], x["tm"]))
    return out[:80]


def main():
    if not KEY:
        print("GEMINI_API_KEY がまだ入っていないので、何もしません")
        return
    cities = json.load(open("public/data/cities.json", encoding="utf-8"))
    want = [ONLY] if ONLY else get_json(SITE + "/api/cities").get("cities", [])
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
        if ONLY or age >= 25:
            todo.append((age, name, c, p))
    todo.sort(key=lambda x: -x[0])
    print("読む市区町村", len(todo), "のうち", min(len(todo), MAX_CITIES))
    os.makedirs(OUT, exist_ok=True)
    for age, name, c, p in todo[:MAX_CITIES]:
        try:
            text, srcs, model = ask(name, c.get("u", ""), today)
        except Limit:
            print("無料の上限に来たので、今日はここまで")
            break
        except Exception as e:
            print("error", name, e)
            continue
        evs = clean(parse(text), c.get("u", ""), today)
        print(name, model, len(evs), "件")
        json.dump({"at": today.isoformat(timespec="seconds"), "city": name, "site": c.get("u", ""), "ev": evs},
                  open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        time.sleep(8)


if __name__ == "__main__":
    main()
