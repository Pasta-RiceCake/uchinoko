# 子連れおでかけのイベント（動物園・水族館・公園・屋内施設などの、親子で行けるイベント）を、都道府県ごとに public/data/odk/<NN>.json に置く
#  - サイトにのせているスポットの公式サイトを読んで、Gemini（無料枠）に今月と来月のイベントを抜き出してもらう
#    （Gemini の Google 検索は無料枠では使えなくなったので、検索はしない）
#  - スポットの公式サイトのURLは tools/odk_sites.json にためておく。まだ無いスポットは Gemini に聞いて、開けるか確かめてから入れる
#  - 1回の実行で MAX_PREFS 県まで。古い県から順に、14日たったら読み直す
import datetime, json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_events import KEY, MODELS, JST, Limit, get_json, fetch, decode, links, text_of, host, base_domain  # noqa: E402

OUT = "public/data/odk"
SITES = "tools/odk_sites.json"
MAX_PREFS = int(os.environ.get("MAX_PREFS", "47"))
ONLY = os.environ.get("PREF", "")
TYPES = ["動物", "水族館", "公園", "屋内", "テーマパーク", "観光"]
EVW = ["イベント", "催し", "もよおし", "行事", "スケジュール", "カレンダー", "お知らせ", "おしらせ", "ニュース", "トピックス", "event", "news", "topics", "schedule"]


def spots():
    s = open("tools/proto.html", encoding="utf-8").read()
    i = s.index("SPOT={") + 5
    d, j = json.JSONDecoder().raw_decode(s[i:])
    k = s.rfind("PREF=[", 0, i) + 5
    prefs = json.JSONDecoder().raw_decode(s[k:])[0]
    return prefs, d


def gem(prompt):
    last = None
    for model in MODELS:
        try:
            r = get_json(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={KEY}",
                         {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}})
        except Limit as e:
            last = e
            print("limit", model, e)
            continue
        except Exception as e:  # 時間切れ（TimeoutError）なども、次のモデルで続ける
            last = e
            print("error", model, str(e)[:200])
            continue
        cand = (r.get("candidates") or [{}])[0]
        return "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", [])), model
    if isinstance(last, Limit):
        raise last
    return "", ""


def opens(u):
    try:
        fu, ct, b = fetch(u)
        return fu if "html" in ct else ""
    except Exception:
        return ""


def find_sites(pref, names, sites):
    """まだURLがわからないスポットの公式サイトを Gemini に聞いて、開けた物だけためる"""
    todo = [n for n in names if n not in sites]
    if not todo:
        return
    prompt = f"""{pref}にある次のスポットの、公式サイトのトップページのURLを答えてください。
知らない・自信がない物は空にしてください（推測で作らない）。ポータルサイトやSNSではなく、そのスポット自身の公式サイトのURL。
答えはJSONだけ。形: {{"スポットの名前":"https://..."}}
スポット: {"、".join(todo)}"""
    text, _ = gem(prompt)
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        got = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        got = {}
    for n in todo:
        u = str(got.get(n) or "").strip()
        fu = opens(u) if re.match(r"https?://", u) else ""
        # 開けなかった物も空で入れて、毎回聞き直さない（14日ごとの読み直しのときにまた聞く）
        sites[n] = fu
        print("  site", n, fu or "-")
        time.sleep(0.5)


def read_spot(u, months):
    """スポットの公式サイトのトップと、イベント・お知らせのページ（3つまで）の文を集める"""
    try:
        fu, ct, b = fetch(u)
    except Exception as e:
        print("  skip", u[:80], str(e)[:60])
        return ""
    html = decode(b, ct)
    out = [f"[{fu}]\n" + text_of(html)[:5000]]
    root = base_domain(host(fu))
    cand, seen = [], {fu}
    for lu, lt in links(html, fu):
        if lu in seen or not host(lu).endswith(root) or re.search(r"\.(jpg|png|gif|pdf|zip)$", lu, re.I):
            continue
        seen.add(lu)
        sc = sum(w in (lt + " " + lu).lower() for w in EVW) + sum(m in lt for m in months)
        if sc:
            cand.append((sc, lu))
    for _, lu in sorted(cand, key=lambda x: -x[0])[:3]:
        try:
            f2, c2, b2 = fetch(lu)
        except Exception:
            continue
        if "html" in c2:
            out.append(f"[{f2}]\n" + text_of(decode(b2, c2))[:6000])
        time.sleep(0.5)
    return "\n\n".join(out)


def ask(pref, names, sites, today):
    m1 = today.strftime("%Y年%-m月")
    m2 = (today.replace(day=1) + datetime.timedelta(days=32)).strftime("%Y年%-m月")
    months = [f"{today.month}月", f"{(today.month % 12) + 1}月"]
    docs = []
    for n in names:
        if sites.get(n):
            t = read_spot(sites[n], months)
            if t:
                docs.append(f"=== {n} の公式サイト ===\n{t}")
    if not docs:
        return "", ""
    prompt = f"""今日は{today.strftime("%Y年%-m月%-d日")}です。下は{pref}のおでかけスポットの公式サイトの文です。
ここに書いてある、{m1}と{m2}に開かれる、赤ちゃん・小さい子ども（0〜6歳くらい）と親が楽しめるイベントを、最大30件あげてください
（えさやり体験、季節のイベント、ショー、親子向けワークショップ、ライトアップなど）。
大人だけ向け・小学生以上だけ向けの物、日にちのわからない物、文に書いていない物は入れないでください。毎日やっている常設の物は入れないでください。
place はスポットの名前（=== の行の名前）。url は、そのイベントがのっているページのURL（[ ] の中のURL）。
答えはJSONだけ。形:
{{"events":[{{"date":"YYYY-MM-DD","end":"YYYY-MM-DD（1日だけなら空）","title":"イベントの名前","place":"スポットの名前","type":"{"/".join(TYPES)} のどれか","url":"…"}}]}}
もし無ければ {{"events":[]}}

""" + "\n\n".join(docs)[:90000]
    return gem(prompt)


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
        if not re.match(r"https?://[^\s]+\.[a-z]{2,}", u):
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
    sites = json.load(open(SITES, encoding="utf-8")) if os.path.exists(SITES) else {}
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
            if age < 999:
                # 読み直しのときは、前に見つからなかったスポットだけ聞き直す
                for n in names:
                    if sites.get(n) == "":
                        sites.pop(n)
            find_sites(p, names, sites)
            json.dump(sites, open(SITES, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
            time.sleep(4)
            text, model = ask(p, names, sites, today)
        except Limit:
            print("無料の上限に来たので、今日はここまで")
            break
        except Exception as e:
            print(p, "とばします", str(e)[:200])
            continue
        evs = clean(text, names, today)
        print(p, model, len(evs), "件", "サイト", sum(1 for n in names if sites.get(n)), "/", len(names))
        json.dump({"at": today.isoformat(timespec="seconds"), "pref": p, "ev": evs, "sp": []},
                  open(f, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        time.sleep(8)


if __name__ == "__main__":
    main()
