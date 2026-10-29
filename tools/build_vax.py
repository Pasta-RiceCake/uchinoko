# 「ワクチン・葉酸・アレルギー」のワクチンの制度（無料になる時期・対象）を、厚生労働省のページと毎月見くらべる
# しくみは build_tax.py と同じ（ページが変わったときだけ Gemini が見くらべ、元のページにない数字は使わない）
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_tax  # noqa: E402

V = "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/kenkou/kekkaku-kansenshou/yobou-sesshu/vaccine/"
SRC = {
    "RSウイルスのワクチン（母子免疫）": [["厚生労働省 RSウイルスワクチン", V + "rs/index.html"]],
    "生後2か月から始まります": [["予防接種スケジュール（国立健康危機管理研究機構）", "https://id-info.jihs.go.jp/relevant/vaccine/topics/040/schedule.html"],
                          ["厚生労働省 5種混合ワクチン", V + "dpt-ipv-hib/index.html"]],
    "風しん（ママは妊娠中は受けられません）": [["厚生労働省 MRワクチン", V + "mr/index.html"]],
}

if __name__ == "__main__":
    build_tax.main(BASE=os.path.join(os.path.dirname(os.path.abspath(__file__)), "vax_base.json"), OUT="public/data/vax.json", SRC=SRC,
                   FORCE=os.environ.get("TAX_FORCE", "") == "1")
