# -*- coding: utf-8 -*-
"""阈值 × 每pp 的网格对比"""
import datetime as dt
import json

import daily_score as ds
import trough

FEE = 0.0012


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
    if r["date"] < "2023-10-01":
        continue
    m = ma20.get(r["date"])
    r["gap"] = (m / r["price"] - 1) * 100 if m else -99
    rows.append(r)

years = (dt.date.fromisoformat(rows[-1]["date"]) - dt.date.fromisoformat(rows[0]["date"])).days / 365.25


def run(rate, thr, base_hi=650):
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
        units += a / (1 + FEE) / r["price"]
        invested += a
        flows.append((r["date"], -a))
        v = units * r["price"]
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    value = units * rows[-1]["price"]
    return dict(invested=invested, value=value, ret=value / invested - 1,
                xirr=xirr(flows + [(rows[-1]["date"], value)]),
                mdd=mdd, annual=invested / years, mx=mx, trig=trig)


print("%5s %5s %10s %9s %9s %8s" % ("阈值", "每pp", "年均投入", "XIRR", "回撤", "单日最高"))
for thr in (1.5, 2.0, 3.0):
    for rate in (200, 250, 300, 350, 400, 600, 800, 1000):
        s = run(rate, thr)
        mark = "  ←预算" if 54000 <= s["annual"] <= 58000 else ""
        print("%5.1f %5d %10s %+9.2f%% %8.2f%% %8s%s" % (
            thr, rate, format(int(s["annual"]), ","), s["xirr"] * 100,
            s["mdd"] * 100, format(int(s["mx"]), ","), mark))
    print()
