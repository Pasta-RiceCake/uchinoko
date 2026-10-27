# 公開データから public/data/ を作る（GitHub Actions で毎月）
#  - hoiku/<都道府県コード>.json : OpenStreetMap の保育園・こども園・幼稚園（© OpenStreetMap contributors, ODbL）
#  - sanin/<都道府県コード>.json : 医療情報ネットの 産科・産婦人科 の病院・診療所と助産所（厚生労働省, PDL1.0）
#  - cities.json               : Wikidata の市区町村コード・公式サイト・位置（CC0）
import csv, io, json, os, re, sys, time, urllib.parse, urllib.request, zipfile

OUT = sys.argv[1] if len(sys.argv) > 1 else "public/data"
UA = {"User-Agent": "uchinoko-techo/1.0 (https://uchinoko.pocket-app.workers.dev)"}
PREF = ["北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県","茨城県","栃木県","群馬県","埼玉県","千葉県","東京都","神奈川県","新潟県","富山県","石川県","福井県","山梨県","長野県","岐阜県","静岡県","愛知県","三重県","滋賀県","京都府","大阪府","兵庫県","奈良県","和歌山県","鳥取県","島根県","岡山県","広島県","山口県","徳島県","香川県","愛媛県","高知県","福岡県","佐賀県","長崎県","熊本県","大分県","宮崎県","鹿児島県","沖縄県"]


def get(url, data=None, timeout=180):
    req = urllib.request.Request(url, data=data, headers=UA)
    for n in range(4):
        try:
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            print("retry", url[:80], e)
            time.sleep(10 * (n + 1))
    raise RuntimeError("fetch failed " + url)


def dump(path, obj):
    path = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def r5(x):
    return round(float(x), 5)


# ---------- 市区町村 ----------
def cities():
    q = """SELECT ?code ?label ?site ?loc WHERE { ?c wdt:P429 ?code; rdfs:label ?label FILTER(lang(?label)="ja")
      OPTIONAL { ?c wdt:P856 ?site } OPTIONAL { ?c wdt:P625 ?loc } }"""
    d = json.loads(get("https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": q, "format": "json"})))
    out = {}
    for b in d["results"]["bindings"]:
        code = re.sub(r"\D", "", b["code"]["value"])[:5]
        if len(code) != 5 or code.endswith("000"):
            continue
        p = int(code[:2])
        if not 1 <= p <= 47:
            continue
        key = PREF[p - 1] + b["label"]["value"]
        o = out.setdefault(key, {"c": code})
        if "site" in b and "u" not in o:
            o["u"] = b["site"]["value"]
        m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", b.get("loc", {}).get("value", ""))
        if m and "p" not in o:
            o["p"] = [r5(m.group(2)), r5(m.group(1))]
    print("cities", len(out))
    dump("cities.json", out)


# ---------- 保育園 ----------
def kind(name):
    if "こども園" in name:
        return "こども園"
    if "小規模" in name:
        return "小規模"
    if re.search("保育園|保育所|保育室|託児|ナーサリー|保育ルーム", name):
        return "保育園"
    if "幼稚園" in name:
        return "幼稚園"
    return "その他"


def hoiku():
    """全国をまとめて1回で取り、いちばん近い市区町村の中心で都道府県に分ける"""
    servers = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
    q = '[out:json][timeout:900];area["ISO3166-1"="JP"][admin_level=2]->.a;(nwr["amenity"~"^(kindergarten|childcare)$"](area.a););out center tags;'
    d = None
    for s in servers:
        try:
            d = json.loads(get(s, urllib.parse.urlencode({"data": q}).encode(), timeout=1000))
            break
        except Exception as e:
            print("overpass", s, e)
    if d is None:
        raise RuntimeError("overpass")
    cs = json.load(open(os.path.join(OUT, "cities.json"), encoding="utf-8"))
    centers = [(v["p"][0], v["p"][1], v["c"][:2]) for v in cs.values() if "p" in v]
    grid = {}
    for la, lo, pc in centers:
        grid.setdefault((int(la * 4), int(lo * 4)), []).append((la, lo, pc))

    def pref_of(la, lo):
        best, bd = None, 1e9
        for r in (0, 1, 2, 3):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    for cla, clo, pc in grid.get((int(la * 4) + dy, int(lo * 4) + dx), []):
                        dd = (cla - la) ** 2 + ((clo - lo) * 0.82) ** 2
                        if dd < bd:
                            best, bd = pc, dd
            if best:
                return best
        return None

    out, seen = {}, set()
    for e in d.get("elements", []):
        t = e.get("tags", {})
        name = t.get("name") or t.get("name:ja")
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")
        if not name or lat is None:
            continue
        k = (name, round(lat, 3), round(lon, 3))
        if k in seen:
            continue
        seen.add(k)
        pc = pref_of(lat, lon)
        if not pc:
            continue
        addr = t.get("addr:full") or "".join(t.get(x, "") for x in ["addr:province", "addr:city", "addr:suburb", "addr:quarter", "addr:neighbourhood", "addr:block_number", "addr:housenumber"])
        out.setdefault(pc, []).append([name, kind(name), r5(lat), r5(lon), addr, t.get("website") or t.get("contact:website") or "", t.get("phone") or t.get("contact:phone") or ""])
    for pc, rows in sorted(out.items()):
        print(pc, len(rows))
        dump(f"hoiku/{pc}.json", rows)
    print("hoiku total", sum(len(r) for r in out.values()))


# ---------- 産院 ----------
MED = "https://www.mhlw.go.jp/content/11121000/"


def find_files():
    names = {b: b + "_20260601.csv.zip" for b in ["01-1_hospital_facility_info", "01-2_hospital_speciality_hours", "02-1_clinic_facility_info", "02-2_clinic_speciality_hours", "04_maternity_home"]}
    try:
        html = get("https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html").decode("utf-8", "replace")
    except RuntimeError:
        html = ""
    for f in re.findall(r"(0[1-4]-?\d?_[a-z_]+_\d{8}\.csv\.zip)", html):
        base = re.sub(r"_\d{8}\.csv\.zip$", "", f)
        if base in names and f > names[base]:
            names[base] = f
    print("med files", names)
    return names


def read_zip(fname):
    z = zipfile.ZipFile(io.BytesIO(get(MED + fname, timeout=600)))
    raw = z.read(z.namelist()[0])
    for enc in ("utf-8-sig", "cp932"):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            pass
    return list(csv.DictReader(io.StringIO(txt)))


def sanin():
    names = find_files()
    out = {}
    for fac, spe, label in [("01-1_hospital_facility_info", "01-2_hospital_speciality_hours", "病院"), ("02-1_clinic_facility_info", "02-2_clinic_speciality_hours", "クリニック")]:
        ids = {}
        for r in read_zip(names[spe]):
            n = r.get("診療科目名", "")
            if n in ("産科", "産婦人科"):
                ids.setdefault(r["ID"], set()).add(n)
        print(label, "産科/産婦人科", len(ids))
        for r in read_zip(names[fac]):
            if r["ID"] not in ids or not r.get("所在地座標（緯度）"):
                continue
            add(out, r, label, "・".join(sorted(ids[r["ID"]])))
    if "04_maternity_home" in names:
        n = 0
        for r in read_zip(names["04_maternity_home"]):
            if r.get("所在地座標（緯度）"):
                add(out, r, "助産院", "")
                n += 1
        print("助産院", n)
    for p, rows in out.items():
        dump(f"sanin/{p}.json", rows)


def add(out, r, label, spec):
    try:
        lat, lon = r5(r["所在地座標（緯度）"]), r5(r["所在地座標（経度）"])
    except ValueError:
        return
    p = (r.get("都道府県コード") or "").zfill(2)[:2]
    url = (r.get("案内用ホームページアドレス") or "").strip()
    if url and not url.startswith("http"):
        url = "https://" + url
    out.setdefault(p, []).append([r.get("正式名称", ""), label, lat, lon, r.get("所在地", ""), url, spec])


if __name__ == "__main__":
    what = os.environ.get("ONLY", "cities,hoiku,sanin").split(",")
    if "cities" in what:
        cities()
    if "sanin" in what:
        sanin()
    if "hoiku" in what:
        if not os.path.exists(os.path.join(OUT, "cities.json")):
            cities()
        hoiku()
