# -*- coding: utf-8 -*-
"""C-2：分档 50/100/650 + 跌破 MA20 超 3% 后每 1pp 加 800"""
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


def amt(r):
    s = r["score"]
    if s < 20:
        a = 50
    elif s < 75:
        a = 100
    else:
        a = 650
        if r["gap"] > 3:
            a += (r["gap"] - 3) * 800
    return a


units = invested = fees = 0.0
peak = mdd = 0.0
flows = []
per_year = collections.Counter()
trig = []
for r in rows:
    a = amt(r)
    net = a / (1 + FEE)
    units += net / r["price"]
    invested += a
    fees += a - net
    flows.append((r["date"], -a))
    per_year[r["date"][:4]] += a
    v = units * r["price"]
    peak = max(peak, v)
    mdd = min(mdd, v / peak - 1)
    if r["score"] >= 75 and r["gap"] > 3:
        trig.append((r["date"], r["score"], r["gap"], a))

value = units * rows[-1]["price"]
ret = value / invested - 1
irr = xirr(flows + [(rows[-1]["date"], value)])

print("区间 %s ~ %s，%d 个交易日，%.2f 年" % (rows[0]["date"], rows[-1]["date"], len(rows), years))
print("规则：<20 → 50；20–75 → 100；≥75 → 650；且跌破 MA20 超 3% 时，每多 1pp 加 800")
print()
print("投入   ¥%s（日均 ¥%.0f，年均 ¥%s）" % (
    format(int(invested), ","), invested / len(rows), format(int(invested / years), ",")))
print("市值   ¥%s" % format(int(value), ","))
print("盈亏   %+.2f%%   XIRR %+.2f%%   最大回撤 %.2f%%" % (ret * 100, irr * 100, mdd * 100))
print("手续费 ¥%.0f" % fees)
print("分年   %s" % " ".join("%s ¥%s" % (k, format(int(v), ",")) for k, v in sorted(per_year.items())))
print()
print("加码触发 %d 天，加码总额 ¥%s，单日最高 ¥%s" % (
    len(trig), format(int(sum(t[3] - 650 for t in trig)), ","),
    format(int(max(t[3] for t in trig)), ",") if trig else "—"))
for t in sorted(trig, key=lambda x: -x[3])[:8]:
    print("   %s 分%.0f 偏离 %.1f%% → ¥%s" % (t[0], t[1], t[2], format(int(t[3]), ",")))

# 对照：现行策略
def cur(s):
    if s <= 50:
        return 100
    if s >= 80:
        return 500
    return int(round((100 + (s - 50) / 30.0 * 400) / 10.0) * 10)


u2 = inv2 = f2 = 0.0
pk2 = md2 = 0.0
fl2 = []
for r in rows:
    a = cur(r["score"])
    net = a / (1 + FEE)
    u2 += net / r["price"]
    inv2 += a
    f2 += a - net
    fl2.append((r["date"], -a))
    v = u2 * r["price"]
    pk2 = max(pk2, v)
    md2 = min(md2, v / pk2 - 1)
v2 = u2 * rows[-1]["price"]
print()
print("对照【A 现行】投入 ¥%s（年均 ¥%s）市值 ¥%s  %+.2f%%  XIRR %+.2f%%  回撤 %.2f%%" % (
    format(int(inv2), ","), format(int(inv2 / years), ","), format(int(v2), ","),
    (v2 / inv2 - 1) * 100, xirr(fl2 + [(rows[-1]["date"], v2)]) * 100, md2 * 100))
