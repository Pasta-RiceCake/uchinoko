# 絵本の定番（見本の BOOKS）を、1冊ずつ楽天の商品ページにつなぐ → public/data/books.json
#  検索結果のページではなく、その本の商品ページに飛べるように。レビューの多い新品で、書名が合う物を選ぶ
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_rank import APP, call, item  # noqa: E402

BOOK_GENRE = 200162  # 本・雑誌・コミック
USED = re.compile(r"中古|USED|ユーズド|訳あり|レンタル|セット|全巻|まとめ売り")


def books():
    s = open("tools/proto.html", encoding="utf-8").read()
    i = s.index("BOOKS=[") + 6
    return json.JSONDecoder().raw_decode(s[i:])[0]


def norm(t):
    return re.sub(r"[\s　・、。！!？?「」『』（）()〜~ー-]", "", t)


def find(title):
    try:
        d = call("search", keyword=title + " 絵本", genreId=BOOK_GENRE, sort="-reviewCount", hits=15, imageFlag=1)
    except Exception as e:
        print("  ng", title, e)
        return None
    key = norm(title)
    for x in d.get("Items", []):
        it = item(x)
        if USED.search(it["n"]) or not it["p"]:
            continue
        if key in norm(it["n"]):
            return {"u": it["u"], "img": it["img"], "p": int(it["p"]), "n": it["n"]}
    return None


def main():
    if not APP:
        print("RAKUTEN_APP_ID がまだ入っていないので、何もしません")
        return
    out = {}
    for g, bs in books():
        for b in bs:
            t = b[0]
            r = find(t)
            print(g, t, "->", r and (r["n"], r["p"]))
            if r:
                out[t] = r
    if out:
        json.dump(out, open("public/data/books.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("books", len(out))


if __name__ == "__main__":
    main()
