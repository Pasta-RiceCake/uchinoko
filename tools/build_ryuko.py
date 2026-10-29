# 「いま、はやっている病気」を、国の感染症の週報（国立健康危機管理研究機構 IDWR速報）から毎週つくる
#  - 定点把握（インフルエンザ・RSウイルスなど）は「1つの病院あたりの患者数」、全数把握（百日せき・はしか）は人数
#  - 最新の週と、その前の週をくらべて、ふえているかを出す
#  - 出力は public/data/ryuko.json。取れなかったときは前の内容をそのまま残す
import csv, datetime, io, json, os, re, sys, unicodedata, urllib.request

OUT = "public/data/ryuko.json"
BASE = "https://id-info.jihs.go.jp/surveillance/idwr/provisional/{y}/{w:02d}/{y}-{w:02d}-{k}.csv"
# 定点把握：サイトでの名前、CSVの名前（NFKC後にふくまれる文字）
TEITEN = [["インフルエンザ", "インフルエンザ"], ["新型コロナ", "COVID-19"], ["RSウイルス", "RSウイルス"], ["プール熱（咽頭結膜熱）", "咽頭結膜熱"],
          ["溶連菌", "A群溶血性レンサ球菌"], ["感染性胃腸炎", "感染性胃腸炎"], ["水ぼうそう", "水痘"], ["手足口病", "手足口病"], ["りんご病", "伝染性紅斑"],
          ["突発性発しん", "突発性発しん"], ["ヘルパンギーナ", "ヘルパンギーナ"], ["おたふくかぜ", "流行性耳下腺炎"]]
ZENSU = [["百日せき", "百日咳"], ["はしか（麻しん）", "麻しん"], ["風しん", "風しん"]]


def get(y, w, k):
    req = urllib.request.Request(BASE.format(y=y, w=w, k=k), headers={"User-Agent": "Mozilla/5.0 (uchinoko-techo; +https://uchinoko.pocket-app.workers.dev)"})
    b = urllib.request.urlopen(req, timeout=40).read()
    return list(csv.reader(io.StringIO(b.decode("cp932", "replace"), newline="")))


def nk(s):
    return unicodedata.normalize("NFKC", s or "").strip()


def num(s):
    s = nk(s).replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def table(rows, sub):
    """病気の名前の行と「報告/定当（累積）」の行を見つけて、{県: {病気: 値}} にする"""
    hi = next(i for i, r in enumerate(rows) if len(r) > 3 and nk(r[1]) == "報告")
    names, cols = rows[hi - 1], {}
    for j in range(1, len(names)):
        if nk(names[j]):
            cols[nk(names[j])] = j
    out = {}
    for r in rows[hi + 1:]:
        if not r or not nk(r[0]):
            continue
        p = nk(r[0])
        if p != "総数" and not re.search(r"[都道府県]$", p):
            continue
        out[p] = {}
        for site, key in sub:
            j = next((c for n, c in cols.items() if key in n), None)
            if j is None:
                continue
            k = j + 1 if sub is TEITEN else j  # 定点は「定当」、全数は「報告」
            out[p][site] = num(r[k]) if k < len(r) else 0.0
    return out


def week_title(rows):
    for r in rows[:4]:
        for c in r:
            m = re.search(r"(\d{4})年(\d+)週\((\d+)月(\d+)日[～〜~-](\d+)月(\d+)日\)", nk(c).replace("~", "～"))
            if m:
                return f"{int(m.group(3))}/{int(m.group(4))}〜{int(m.group(5))}/{int(m.group(6))}"
    return ""


def latest():
    t = datetime.date.today()
    y, w, _ = t.isocalendar()
    for i in range(0, 6):
        yy, ww = y, w - i
        if ww < 1:
            yy, ww = y - 1, 52 + ww
        try:
            return yy, ww, get(yy, ww, "teiten")
        except Exception:
            continue
    raise RuntimeError("no data")


def prev_w(y, w):
    return (y - 1, 52) if w == 1 else (y, w - 1)


def main():
    try:
        y, w, t_now = latest()
        py, pw = prev_w(y, w)
        t_prev = get(py, pw, "teiten")
        z_now, z_prev = get(y, w, "zensu"), get(py, pw, "zensu")
        a, b = table(t_now, TEITEN), table(t_prev, TEITEN)
        za, zb = table(z_now, ZENSU), table(z_prev, ZENSU)
    except Exception as e:
        print("fail, keep old:", e)
        return
    pref = {}
    for p in a:
        pref[p] = {k: [a[p].get(k, 0), b.get(p, {}).get(k, 0)] for k, _ in TEITEN if k in a[p]}
        pref[p].update({k: [za.get(p, {}).get(k, 0), zb.get(p, {}).get(k, 0)] for k, _ in ZENSU if k in za.get(p, {})})
    if "総数" not in pref or len(pref) < 40:
        print("odd table, keep old", len(pref))
        return
    print(y, w, week_title(t_now), "総数:", pref["総数"])
    json.dump({"y": y, "w": w, "range": week_title(t_now), "made": datetime.date.today().isoformat(), "zensu": [k for k, _ in ZENSU],
               "src": "https://id-info.jihs.go.jp/surveillance/idwr/provisional/%d/%02d/index.html" % (y, w), "pref": pref},
              open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    print("wrote", OUT, os.path.getsize(OUT))


if __name__ == "__main__":
    main()
