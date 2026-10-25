# -*- coding: utf-8 -*-
"""2023-03 至今：现行定投 vs 分档定投 对比"""
import datetime as dt
import json

import daily_score as ds
import trough

FEE = 0.0012
START = "2023-10-01"


def xirr(flows):
    lo, hi = -0.99, 5.0
    for _ in range(200):
        mid = (lo + hi) / 2
        v = sum(cf / ((1 + mid) ** ((dt.date.fromisoformat(d) - dt.date.fromisoformat(flows[0][0])).days / 365.0))
                for d, cf in flows)
        if v > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def simulate(rows, fn):
    units = invested = fees = 0.0
    peak = 0.0
    mdd = 0.0
    flows = []
    for r in rows:
        a = fn(r["score"])
        net = a / (1 + FEE)
        units += net / r["price"]
        invested += a
        fees += a - net
        flows.append((r["date"], -a))
        v = units * r["price"]
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    value = units * rows[-1]["price"]
    flows.append((rows[-1]["date"], value))
    return dict(invested=invested, value=value, pnl=value - invested,
                ret=value / invested - 1, units=units, fees=fees,
                xirr=xirr(flows), mdd=mdd, n=len(rows))


cfg = json.load(open("config.json", encoding="utf-8"))
frames = ds.load_frames(cfg)
rows = [r for r in trough.build(frames) if r["date"] >= START]
years = (dt.date.fromisoformat(rows[-1]["date"]) - dt.date.fromisoformat(rows[0]["date"])).days / 365.25

print("区间 %s ~ %s，%d 个交易日，%.2f 年" % (rows[0]["date"], rows[-1]["date"], len(rows), years))
sc = [r["score"] for r in rows]
print("谷底分 均值 %.0f，区间 %.0f~%.0f" % (sum(sc) / len(sc), min(sc), max(sc)))

# ---------- A：现行策略 ----------
def cur(s):
    if s <= 50:
        return 100
    if s >= 80:
        return 500
    return int(round((100 + (s - 50) / 30.0 * 400) / 10.0) * 10)


a = simulate(rows, cur)
print("\n【A 现行】50 分以下 100，80 分以上 500，中间线性")
print("  投入 ¥%s（日均 ¥%.0f，年均 ¥%s）" % (
    format(int(a["invested"]), ","), a["invested"] / len(rows),
    format(int(a["invested"] / years), ",")))
print("  市值 ¥%s  盈亏 %+.2f%%  XIRR %+.2f%%  最大回撤 %.2f%%  手续费 ¥%.0f" % (
    format(int(a["value"]), ","), a["ret"] * 100, a["xirr"] * 100, a["mdd"] * 100, a["fees"]))

# ---------- B：分档，求 >75 那一档的金额 ----------
n_low = sum(1 for s in sc if s < 20)
n_mid = sum(1 for s in sc if 20 <= s < 75)
n_high = sum(1 for s in sc if s >= 75)
print("\n档位天数：<20 有 %d 天，20–75 有 %d 天，≥75 有 %d 天" % (n_low, n_mid, n_high))
target = 56000 * years
x = (target - 50 * n_low - 100 * n_mid) / float(n_high)
print("若一年想投 ¥56,000（本期目标 ¥%s），≥75 那档需要 ¥%.0f/天" % (format(int(target), ","), x))

for X in (500, 600, 700, 800, x, 900):
    b = simulate(rows, lambda s, X=X: 50 if s < 20 else (100 if s < 75 else int(round(X / 10.0) * 10)))
    print("  X=%4.0f → 投入 ¥%s（年均 ¥%s）市值 ¥%s  %+.2f%%  XIRR %+.2f%%  回撤 %.2f%%" % (
        X, format(int(b["invested"]), ","), format(int(b["invested"] / years), ","),
        format(int(b["value"]), ","), b["ret"] * 100, b["xirr"] * 100, b["mdd"] * 100))
