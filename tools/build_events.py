# 家族のいる市区町村の子育てイベントを、Gemini（無料枠）に公式サイトから探してもらい public/data/events/ に置く
#  - 1回の実行で MAX_CITIES 市まで。古い市から順に、25日たったら読み直す
#  - 無料の上限に来たら（429）、そこで止めて、作れた分だけ保存する
import base64, datetime, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

OUT = "public/data/events"
SITE = os.environ.get("SITE", "https://uchinoko.pocket-app.workers.dev")
KEY = os.environ.get("GEMINI_API_KEY", "")
MODELS = [m for m in os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite,gemini-flash-lite-latest,gemini-3-flash-preview").split(",") if m]
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
            raise Limit(e.read()[:1500])
        raise RuntimeError(f"{e.code} {e.read()[:300]}")


def host(u):
    try:
        return urllib.parse.urlparse(u).hostname or ""
    except ValueError:
        return ""


def base_domain(h):
    p = h.split(".")
    return ".".join(p[-3:]) if h.endswith((".lg.jp", ".or.jp", ".ne.jp", ".co.jp", ".ac.jp", ".go.jp")) else ".".join(p[-2:])


# ---------- 市の公式サイトを読む ----------
WORDS = ["子育て", "子ども", "こども", "乳幼児", "赤ちゃん", "親子", "支援センター", "児童館", "ひろば", "離乳食", "両親学級", "母親学級", "パパママ", "プレママ", "妊娠", "妊婦", "教室", "講座", "イベント", "催し", "行事", "予定", "カレンダー", "日程", "おはなし会", "育児相談", "健康相談", "保健センター"]
STRONG = ["支援センター", "児童館", "離乳食", "両親学級", "母親学級", "パパママ", "プレママ", "親子教室", "赤ちゃん", "乳幼児", "ひろば", "おはなし会", "育児相談", "日程", "予定", "カレンダー"]


def fetch(u, limit=3_000_000):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (uchinoko-techo; +https://uchinoko.pocket-app.workers.dev)"})
    r = urllib.request.urlopen(req, timeout=40)
    ct = r.headers.get("content-type", "")
    b = r.read(limit + 1)
    if len(b) > limit:
        raise RuntimeError("too big")
    return r.geturl(), ct, b


def decode(b, ct):
    m = re.search(r"charset=([\w-]+)", ct) or re.search(rb'charset=["\']?([\w-]+)', b[:3000])
    enc = (m.group(1).decode() if isinstance(m.group(1), bytes) else m.group(1)) if m else "utf-8"
    try:
        return b.decode(enc, "replace")
    except LookupError:
        return b.decode("utf-8", "replace")


def links(html, base):
    out = []
    for m in re.finditer(r'<a\s[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', html, re.S | re.I):
        t = re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip()
        out.append((urllib.parse.urljoin(base, m.group(1).strip()), t))
    return out


def text_of(html):
    html = re.sub(r"(?is)<(script|style|noscript|header|footer|nav)[^>]*>.*?</\1>", " ", html)
    t = re.sub(r"(?s)<br\s*/?>|</(p|div|li|tr|h\d)>", "\n", html)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&nbsp;", " ", t)
    t = re.sub(r"[ \t　]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def score(t, months):
    s = sum(2 for w in STRONG if w in t) + sum(1 for w in WORDS if w in t)
    if any(m in t for m in months):
        s += 4
    return s


def crawl(site, today, max_pages=80):
    """公式サイトのトップから、子育てのイベントがのっていそうなページとPDFを集める"""
    if not site:
        return []
    m1, m2 = today.month, (today.month % 12) + 1
    months = [f"{m1}月", f"{m2}月", f"{today.year}年{m1}月"]
    root = base_domain(host(site))
    seen, queue, pages, pdfs = set(), [(site, "トップ", 0, 99)], [], {}
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
        if "pdf" in ct or fu.lower().endswith(".pdf"):
            continue
        if "html" not in ct:
            continue
        html = decode(b, ct)
        t = text_of(html)
        sc = score(t[:20000], months)
        if depth > 0 and sc >= 6:
            pages.append({"u": fu, "text": t[:12000], "label": label, "sc": sc})
            for lu, lt in links(html, fu):
                if lu.lower().endswith(".pdf") and lu not in pdfs:
                    pdfs[lu] = (lt, sc + 2 * score(lt + " " + lu, months))
        if depth >= 3:
            continue
        for lu, lt in links(html, fu):
            h = host(lu)
            if not h.endswith(root) or lu in seen or re.search(r"\.(jpg|png|gif|zip|xlsx?|docx?|pdf)$", lu, re.I):
                continue
            ls = score(lt, months)
            if ls >= 1 or (depth == 0 and "kosodate" in lu):
                queue.append((lu, lt, depth + 1, ls - depth))
        time.sleep(0.5)
    pages.sort(key=lambda p: -p["sc"])
    pages = pages[:8]
    # 日程表はPDFのことが多いので、よさそうなPDFを5つまで読む
    total = 0
    for lu, (lt, sc) in sorted(pdfs.items(), key=lambda x: -x[1][1])[:12]:
        if sum(1 for p in pages if "pdf" in p) >= 8:
            break
        try:
            fu, ct, b = fetch(lu, limit=9_000_000)
        except Exception as e:
            print("  skip pdf", lu[-60:], str(e)[:60])
            continue
        if total + len(b) > 12_000_000:
            continue
        total += len(b)
        pages.append({"u": fu, "pdf": b, "label": lt, "sc": sc})
    return pages


def ask(city, site, today):
    m1 = today.strftime("%Y年%-m月")
    m2 = (today.replace(day=1) + datetime.timedelta(days=32)).strftime("%Y年%-m月")
    pages = crawl(site, today)
    print(" ", city, "pages", [(p["sc"], p["label"][:20], p["u"][-60:]) for p in pages])
    if not pages:
        return "", [], ""
    # PDFは1つずつ、ページはまとめてGeminiに読んでもらう（1回に多く渡すと取りこぼすため）
    groups, srcs, names = [[]], [], set()
    for p in pages:
        if "pdf" in p:
            fn = p["u"].rsplit("/", 1)[-1]
            if fn in names:
                continue
            names.add(fn)
            groups.append([{"text": f"\n--- 資料（PDF）URL: {p['u']} 見出し: {p['label']} ---"},
                           {"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(p["pdf"]).decode()}}])
        else:
            groups[0].append({"text": f"\n--- 資料 URL: {p['u']} 見出し: {p['label']} ---\n{p['text']}"})
        srcs.append(p["u"])
    prompt = f"""下の資料は、{city}の公式サイト（{site}）から集めたものです。今日は{today.strftime("%Y年%-m月%-d日")}です。
資料にのっている、{m1}と{m2}に開かれる、赤ちゃん・乳幼児とその親、または妊婦さん向けの催しを、もれなく抜き出してください。
対象: 子育て支援センターや児童館の催し、親子教室・赤ちゃん教室・乳幼児教室、離乳食教室、育児相談・身体測定、両親学級・母親学級・プレママ教室、図書館の赤ちゃん向けおはなし会など。
大人だけ向けの相談会や、子育てと関係のない催しは入れないでください。
資料に書いてあることだけを使い、日にちが書いていないものは入れないでください。表になっている日程は、1行ずつ1件にしてください。「毎週火曜」などは、{m1}と{m2}のそれぞれの日に分けてください。
答えはJSONだけで、ほかの文は書かないでください。形:
{{"events":[{{"date":"YYYY-MM-DD","time":"10:00〜11:30","title":"催しの名前","place":"場所","target":"対象（例：0歳児と保護者）","kind":"次のどれか1つ: {" / ".join(KINDS)}","need":"予約がいるか・持ち物など短く","url":"のっていた資料のURL"}}]}}
1つの資料で最大60件。見つからなければ {{"events":[]}}。"""
    allev, used = [], ""
    for g in groups:
        if not g:
            continue
        text, model = gem([{"text": prompt}] + g)
        used = model
        allev += parse(text)
        time.sleep(4)
    return json.dumps({"events": allev}, ensure_ascii=False), srcs, used


def gem(parts):
    last = None
    for model in MODELS:
        try:
            r = get_json(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={KEY}",
                         {"contents": [{"parts": parts}], "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}})
        except Limit as e:
            last = e
            print("limit", model, str(e)[-200:])
            continue
        except RuntimeError as e:
            last = e
            print("error", model, str(e)[:200])
            continue
        cand = (r.get("candidates") or [{}])[0]
        return "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", [])), model
    if isinstance(last, Limit):
        raise last
    print("  gemini failed", last)
    return "", ""


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0)).get("events", [])
    except json.JSONDecodeError:
        return []


def guess_kind(x):
    for k in KINDS:
        if x.startswith(k):
            return k
    if re.search("妊|プレママ|プレパパ|両親|母親学級|パパママ|マタニティ", x):
        return "両親学級・妊婦"
    if re.search("離乳食|健康|相談|測定|健診|歯", x):
        return "離乳食・健康"
    if re.search("支援センター|児童館|ひろば|広場|プラザ", x):
        return "支援センター・児童館"
    if re.search("教室|講座|クラス|ベビー|リトミック|おはなし|ふれあい", x):
        return "親子教室"
    return "おでかけ・その他"


def clean(evs, site, today, srcs=()):
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
        if srcs and u not in srcs:
            u = ""
        k = (d, t)
        if k in seen:
            continue
        seen.add(k)
        kind = guess_kind(str(e.get("kind", "")) + " " + t + " " + str(e.get("place", "")) + " " + str(e.get("target", "")))
        out.append({"d": d.isoformat(), "tm": str(e.get("time", ""))[:30], "t": t, "pl": str(e.get("place", ""))[:60],
                    "to": str(e.get("target", ""))[:40], "k": kind, "n": str(e.get("need", ""))[:80], "u": u})
    out.sort(key=lambda x: (x["d"], x["tm"]))
    return out[:150]


def probe():
    ms = get_json(f"https://generativelanguage.googleapis.com/v1beta/models?key={KEY}&pageSize=200").get("models", [])
    names = [m["name"].split("/")[1] for m in ms if "generateContent" in m.get("supportedGenerationMethods", [])]
    print("models", names)
    for m in [x for x in names if "flash" in x][:12]:
        for tools in ([], [{"google_search": {}}]):
            try:
                r = get_json(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={KEY}",
                             {"contents": [{"parts": [{"text": "倉敷市の公式サイトのURLを1つだけ答えて"}]}], "tools": tools})
                t = "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
                print("OK", m, bool(tools), t[:80].replace("\n", " "))
            except Limit as e:
                print("429", m, bool(tools), str(e)[-400:].replace("\\n", " "))
            except Exception as e:
                print("ERR", m, bool(tools), str(e)[:200])
            time.sleep(4)


def main():
    if os.environ.get("PROBE") and KEY:
        return probe()
    if not KEY:
        print("GEMINI_API_KEY がまだ入っていないので、何もしません")
        return
    if not os.path.exists("public/data/cities.json"):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import build_data
        build_data.OUT = "public/data"
        build_data.cities()
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
        evs = clean(parse(text), c.get("u", ""), today, srcs)
        print(name, model, len(evs), "件")
        json.dump({"at": today.isoformat(timespec="seconds"), "city": name, "site": c.get("u", ""), "ev": evs},
                  open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        time.sleep(8)


if __name__ == "__main__":
    main()
