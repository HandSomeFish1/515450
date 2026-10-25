# -*- coding: utf-8 -*-
"""C-3：阈值 1.5%，扫描每 1pp 的加码金额"""
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


cfg = json.load(open("config.json", encoding="utf-8"))
frames = ds.load_frames(cfg)
adj = frames["nav_adj"]
ma20 = {}
for i in range(19, len(adj)):
    ma20[adj[i][0]] = sum(p for _, p in adj[i - 19:i + 1]) / 20.0

rows = []
for r in trough.build(frames):
    if r["date"] < START:
        continue
    m = ma20.get(r["date"])
    r["gap"] = (m / r["price"] - 1) * 100 if m else -99
    rows.append(r)

years = (dt.date.fromisoformat(rows[-1]["date"]) - dt.date.fromisoformat(rows[0]["date"])).days / 365.25


def run(rate, thr=1.5, base_hi=650):
    units = invested = 0.0
    peak = mdd = 0.0
    flows = []
    mx = 0
    trig = 0
    for r in rows:
        s = r["score"]
        if s < 20:
            a = 50
        elif s < 75:
            a = 100
        else:
            a = base_hi
            if r["gap"] > thr:
                a += (r["gap"] - thr) * rate
                trig += 1
        mx = max(mx, a)
        net = a / (1 + FEE)
        units += net / r["price"]
        invested += a
        flows.append((r["date"], -a))
        v = units * r["price"]
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    value = units * rows[-1]["price"]
    return dict(invested=invested, value=value, ret=value / invested - 1,
                xirr=xirr(flows + [(rows[-1]["date"], value)]),
                mdd=mdd, annual=invested / years, mx=mx, trig=trig)


print("阈值 1.5%%，基础档 50/100/650\n")
print("%6s %10s %12s %9s %9s %10s" % ("每pp", "年均投入", "投入合计", "XIRR", "回撤", "单日最高"))
best = None
for rate in (0, 200, 400, 500, 600, 700, 800, 900, 1000, 1200, 1500, 2000):
    s = run(rate)
    print("%6d %10s %12s %+9.2f%% %8.2f%% %10s" % (
        rate, format(int(s["annual"]), ","), format(int(s["invested"]), ","),
        s["xirr"] * 100, s["mdd"] * 100, format(int(s["mx"]), ",")))
    if 52000 <= s["annual"] <= 60000 and (best is None or s["xirr"] > best[1]):
        best = (rate, s["xirr"], s["annual"])

print()
if best:
    print("预算 5.2–6.0 万内 XIRR 最优：每 pp %d 元 → 年均 ¥%s，XIRR %+.2f%%" % (
        best[0], format(int(best[2]), ","), best[1] * 100))
s = run(best[0]) if best else None
if s:
    print("  投入 ¥%s / 市值 ¥%s / %+.2f%% / 回撤 %.2f%% / 触发 %d 天 / 单日最高 ¥%s" % (
        format(int(s["invested"]), ","), format(int(s["value"]), ","),
        s["ret"] * 100, s["mdd"] * 100, s["trig"], format(int(s["mx"]), ",")))
