# -*- coding: utf-8 -*-
"""策略 D：分档 100/200/500 + 第三档按偏离幅度线性/指数加码"""
import collections
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
    peak = mdd = 0.0
    flows = []
    per_year = collections.Counter()
    extras = []
    for r in rows:
        a = float(fn(r))
        net = a / (1 + FEE)
        units += net / r["price"]
        invested += a
        fees += a - net
        flows.append((r["date"], -a))
        per_year[r["date"][:4]] += a
        v = units * r["price"]
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
        if a > 500:
            extras.append((r["date"], r["score"], r["gap"], a))
    value = units * rows[-1]["price"]
    flows.append((rows[-1]["date"], value))
    return dict(invested=invested, value=value, ret=value / invested - 1,
                xirr=xirr(flows), mdd=mdd, fees=fees, n=len(rows),
                per_year=dict(per_year), extras=extras)


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
    r["ma20"] = m
    r["gap"] = (m / r["price"] - 1) * 100 if m else -99
    rows.append(r)

years = (dt.date.fromisoformat(rows[-1]["date"]) - dt.date.fromisoformat(rows[0]["date"])).days / 365.25
print("区间 %s ~ %s，%d 个交易日，%.2f 年" % (rows[0]["date"], rows[-1]["date"], len(rows), years))


def base(s):
    return 100 if s < 20 else (200 if s < 75 else 500)


def d_amount(r, linear_per_pct=100):
    a = base(r["score"])
    if r["score"] >= 75:
        g = r["gap"]
        if 0 <= g <= 2:
            a += linear_per_pct * g
        elif g > 2:
            a += 100 * (3 ** (g - 2))
    return a


for name, fn in (
    ("D 原版（0-2% 每 1% 加 100）", lambda r: d_amount(r, 100)),
    ("D-变体（0-2% 每 1% 加 500）", lambda r: d_amount(r, 500)),
):
    s = simulate(rows, fn)
    print("\n【%s】" % name)
    print("  投入 ¥%s（日均 ¥%.0f，年均 ¥%s）" % (
        format(int(s["invested"]), ","), s["invested"] / len(rows), format(int(s["invested"] / years), ",")))
    print("  市值 ¥%s  盈亏 %+.2f%%  XIRR %+.2f%%  最大回撤 %.2f%%" % (
        format(int(s["value"]), ","), s["ret"] * 100, s["xirr"] * 100, s["mdd"] * 100))
    print("  分年: %s" % " ".join("%s ¥%s" % (k, format(int(v), ",")) for k, v in sorted(s["per_year"].items())))
    if s["extras"]:
        mx = max(s["extras"], key=lambda x: x[3])
        print("  加码>500 的天数 %d，单日最高 ¥%s（%s gap %.1f%%）" % (
            len(s["extras"]), format(int(mx[3]), ","), mx[0], mx[2]))
        for e in sorted(s["extras"], key=lambda x: -x[3])[:5]:
            print("     %s 分%.0f gap %.1f%% → ¥%s" % (e[0], e[1], e[2], format(int(e[3]), ",")))
