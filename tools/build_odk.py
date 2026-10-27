# 子連れおでかけのイベント（動物園・水族館・公園・屋内施設などの、親子で行けるイベント）を、都道府県ごとに public/data/odk/<NN>.json に置く
#  - Gemini（無料枠）に Google 検索を使わせて、今月と来月のイベントを探してもらう
#  - サイトにのせているスポットの名前も渡して、そこのイベントを優先して探す（お気に入りのスポットのイベントが出るように）
#  - 1回の実行で MAX_PREFS 県まで。古い県から順に、14日たったら読み直す
import datetime, json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_events import KEY, MODELS, JST, Limit, get_json  # noqa: E402

OUT = "public/data/odk"
MAX_PREFS = int(os.environ.get("MAX_PREFS", "47"))
ONLY = os.environ.get("PREF", "")
TYPES = ["動物", "水族館", "公園", "屋内", "テーマパーク", "観光"]


def spots():
    s = open("tools/proto.html", encoding="utf-8").read()
    i = s.index("SPOT={") + 5
    d, j = json.JSONDecoder().raw_decode(s[i:])
    k = s.rfind("PREF=[", 0, i) + 5
    prefs = json.JSONDecoder().raw_decode(s[k:])[0]
    return prefs, d


def ask(pref, names, today):
    m1 = today.strftime("%Y年%-m月")
    m2 = (today.replace(day=1) + datetime.timedelta(days=32)).strftime("%Y年%-m月")
    prompt = f"""今日は{today.strftime("%Y年%-m月%-d日")}です。Google 検索で調べて、{pref}で{m1}と{m2}に開かれる、
赤ちゃん・小さい子ども（0〜6歳くらい）と親が楽しめるおでかけイベントを、最大30件あげてください。
動物園・水族館・公園・科学館・博物館・ショッピングモール・テーマパーク・道の駅などのイベント（えさやり体験、季節のイベント、ショー、親子向けワークショップ、ライトアップなど）。
次のスポットのイベントがあれば、優先して入れてください: {"、".join(names)}
大人だけ向け・小学生以上だけ向けの物、日にちのわからない物、検索で確かめられなかった物は入れないでください。毎日やっている常設の物は入れないでください。
url には、そのイベントがのっている公式のページのURLを入れてください（わからなければ空）。
答えはJSONだけで、ほかの文は書かないでください。形:
{{"events":[{{"date":"YYYY-MM-DD","end":"YYYY-MM-DD（1日だけなら空）","title":"イベントの名前","place":"スポットの名前","type":"{"/".join(TYPES)} のどれか","url":"…"}}]}}"""
    last = None
    for model in MODELS:
        try:
            r = get_json(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={KEY}",
                         {"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}], "generationConfig": {"temperature": 0.1}})
        except Limit as e:
            last = e
            print("limit", model, str(e)[-200:])
            continue
        except RuntimeError as e:
            last = e
            print("error", model, str(e)[:200])
            continue
        cand = (r.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
        grounded = bool((cand.get("groundingMetadata") or {}).get("groundingChunks"))
        return text, model, grounded
    if isinstance(last, Limit):
        raise last
    return "", "", False


def clean(text, names, today):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return []
    try:
        evs = json.loads(m.group(0)).get("events", [])
    except json.JSONDecodeError:
        return []
    lo, hi = today.date(), (today + datetime.timedelta(days=62)).date()
    out, seen = [], set()
    for e in evs:
        try:
            d = datetime.date.fromisoformat(str(e.get("date", ""))[:10])
        except ValueError:
            continue
        try:
            end = datetime.date.fromisoformat(str(e.get("end", ""))[:10])
        except ValueError:
            end = d
        if end < lo or d > hi or (end - d).days > 92:
            continue
        t, pl = str(e.get("title", "")).strip()[:50], str(e.get("place", "")).strip()[:40]
        if not t or not pl or (t, pl) in seen:
            continue
        seen.add((t, pl))
        u = str(e.get("url", "")).strip()
        if not re.match(r"https?://[^\s]+\.[a-z]{2,}", u) or "vertexaisearch" in u or "google.com" in u:
            u = ""
        ty = str(e.get("type", ""))
        # サイトのスポットと同じ場所なら、そのスポットの名前にそろえる（お気に入りで出せるように）
        spot = next((n for n in names if n in pl or (len(pl) >= 4 and pl in n)), "")
        out.append({"d": max(d, lo).isoformat(), "e": end.isoformat() if end != d else "", "t": t, "pl": spot or pl, "ty": ty if ty in TYPES else "観光", "u": u})
    out.sort(key=lambda x: x["d"])
    return out[:40]


def main():
    if not KEY:
        print("GEMINI_API_KEY がまだ入っていないので、何もしません")
        return
    prefs, sp = spots()
    today = datetime.datetime.now(JST)
    todo = []
    for i, p in enumerate(prefs):
        if ONLY and p != ONLY:
            continue
        f = os.path.join(OUT, f"{i + 1:02d}.json")
        age = 999
        if os.path.exists(f):
            age = (today - datetime.datetime.fromisoformat(json.load(open(f, encoding="utf-8"))["at"])).days
        if ONLY or age >= 14:
            todo.append((age, p, f))
    todo.sort(key=lambda x: -x[0])
    print("読む都道府県", len(todo))
    os.makedirs(OUT, exist_ok=True)
    for age, p, f in todo[:MAX_PREFS]:
        names = [x[0] for x in sp.get(p, [])]
        try:
            text, model, grounded = ask(p, names, today)
        except Limit:
            print("無料の上限に来たので、今日はここまで")
            break
        evs = clean(text, names, today)
        print(p, model, "検索あり" if grounded else "検索なし", len(evs), "件")
        if not grounded or not evs:
            continue
        json.dump({"at": today.isoformat(timespec="seconds"), "pref": p, "ev": evs},
                  open(f, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        time.sleep(10)


if __name__ == "__main__":
    main()
