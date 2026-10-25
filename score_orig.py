# -*- coding: utf-8 -*-
"""导出最初的五因子温度分序列"""
import json
import statistics as st

import dca_core as bt

cfg = json.load(open("config.json", encoding="utf-8"))
rows = bt.build_daily_scores(cfg)

data = [[r["date"], round(r["price"], 4), r["score"]] for r in rows]
json.dump(data, open("score_series.json", "w", encoding="utf-8"), ensure_ascii=False)

sc = [r["score"] for r in rows]
print("样本 %s ~ %s，%d 天" % (rows[0]["date"], rows[-1]["date"], len(rows)))
print("分数 %.0f~%.0f，均值 %.0f，标准差 %.0f" % (min(sc), max(sc), st.mean(sc), st.pstdev(sc)))
for lo, hi, name in ((0, 20, "极度低估"), (21, 40, "偏冷"), (41, 60, "中性"), (61, 80, "偏热"), (81, 100, "极度高估")):
    c = sum(1 for s in sc if lo <= s <= hi)
    print("  %3d–%3d %-4s %4d 天（%.0f%%）" % (lo, hi, name, c, 100.0 * c / len(sc)))
print("最新：%s 温度 %d" % (rows[-1]["date"], rows[-1]["score"]))
