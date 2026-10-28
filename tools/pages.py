# メニューのページごとに URL を分ける（Google 検索に1ページずつ出るように）
#  - public/<ページ>/index.html を作る（中身は index.html と同じで、題名・説明・正しいURLだけちがう）
#  - public/sitemap.xml と public/robots.txt も作る
#  - 自分の記録だけのページ（家事・買い物・カレンダーなど）は分けない
# real.py の最後に呼ばれる
import json, os, re, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://uchinoko.pocket-app.workers.dev"
PRIVATE = {"cal", "fufu", "shop", "chores", "contacts", "visits", "baby", "appset", "kise", "homeedit", "shareinfo", "menu", "sync",
           "wants", "clothes", "azuke", "rinyu", "bplan", "names", "events"}
EXTRA = {"privacy": ("プライバシーポリシー", "うちの子手帳のプライバシーポリシーです。")}


def build():
    p = os.path.join(ROOT, "public/index.html")
    s = open(p, encoding="utf-8").read()
    labels = {}
    for k in ("MENU_P", "MENU_M"):
        i = s.index("const " + k + "=")
        j = s.index("\n];", i) if "\n];" in s[i:i + 20000] else s.index("]]]];", i)
        for key, lab in re.findall(r'\["([a-z]+)","([^"]+)","[a-z0-9_]+","[a-z]+"\]', s[i:i + 20000]):
            labels.setdefault(key, lab)
    i = s.index("const MSUB={")
    sub = dict(re.findall(r'([a-z]+):"([^"]*)"', s[i:s.index("};", i)]))
    pages = {k: (v, sub.get(k, "")) for k, v in labels.items() if k not in PRIVATE}
    pages.update({k: v for k, v in EXTRA.items() if k in labels or True})
    # どのページが URL を持つかを画面に教える
    js = "const SEO_PAGES=" + json.dumps({k: v[0] for k, v in pages.items()}, ensure_ascii=False) + ";\n"
    assert "function render(keep){\n" in s
    s = s.replace("function render(keep){\n", js + "function render(keep){\n  try{syncPath()}catch(_){}\n", 1)
    open(p, "w", encoding="utf-8").write(s)
    base_desc = "妊娠中から子育て中まで、無料で使える子育て手帳「うちの子手帳」。"
    urls = [SITE + "/"]
    for k, (lab, d) in pages.items():
        title = f"{lab}｜うちの子手帳"
        desc = (d + "。" if d else "") + base_desc
        h = s.replace("<title>うちの子手帳</title>", f"<title>{title}</title>", 1)
        h = re.sub(r'<meta name="description" content="[^"]*">',
                   f'<meta name="description" content="{desc}">\n<link rel="canonical" href="{SITE}/{k}/">\n<meta property="og:title" content="{title}">\n<meta property="og:description" content="{desc}">\n<meta property="og:url" content="{SITE}/{k}/">\n<meta property="og:type" content="article">',
                   h, count=1)
        d_ = os.path.join(ROOT, "public", k)
        os.makedirs(d_, exist_ok=True)
        open(os.path.join(d_, "index.html"), "w", encoding="utf-8").write(h)
        urls.append(f"{SITE}/{k}/")
    # トップにも canonical
    s2 = re.sub(r'(<meta name="description" content="[^"]*">)', r'\1\n<link rel="canonical" href="' + SITE + '/">', s, count=1)
    open(p, "w", encoding="utf-8").write(s2)
    # 前に作ったページで、もう無いものは消す
    for n in os.listdir(os.path.join(ROOT, "public")):
        f = os.path.join(ROOT, "public", n, "index.html")
        if os.path.isfile(f) and n not in pages and os.path.isfile(os.path.join(ROOT, "public", n, ".page")):
            shutil.rmtree(os.path.join(ROOT, "public", n))
    for k in pages:
        open(os.path.join(ROOT, "public", k, ".page"), "w").write("")
    open(os.path.join(ROOT, "public/sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        "".join(f"<url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    open(os.path.join(ROOT, "public/robots.txt"), "w", encoding="utf-8").write(f"User-agent: *\nDisallow: /api/\nDisallow: /j/\nSitemap: {SITE}/sitemap.xml\n")
    print("pages", len(pages))


if __name__ == "__main__":
    build()
