# -*- coding: utf-8 -*-
"""策略 C：分档 + 第三档按「价格低于 20 日线的幅度」加码"""
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
    extra_total = 0.0
    extra_days = 0
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
        if r.get("extra"):
            extra_total += r["extra"]
            extra_days += 1
    value = units * rows[-1]["price"]
    flows.append((rows[-1]["date"], value))
    return dict(invested=invested, value=value, ret=value / invested - 1,
                xirr=xirr(flows), mdd=mdd, fees=fees, n=len(rows),
                per_year=dict(per_year), extra_total=extra_total, extra_days=extra_days)


cfg = json.load(open("config.json", encoding="utf-8"))
frames = ds.load_frames(cfg)
adj = frames["nav_adj"]
ma20_map = {}
for i in range(19, len(adj)):
    ma20_map[adj[i][0]] = sum(p for _, p in adj[i - 19:i + 1]) / 20.0

rows = []
for r in trough.build(frames):
    if r["date"] < START:
        continue
    ma = ma20_map.get(r["date"])
    r["ma20"] = ma
    r["gap"] = (ma / r["price"] - 1) * 100 if ma else 0.0     # 价格低于均线的百分比
    rows.append(r)

years = (dt.date.fromisoformat(rows[-1]["date"]) - dt.date.fromisoformat(rows[0]["date"])).days / 365.25
print("区间 %s ~ %s，%d 个交易日，%.2f 年" % (rows[0]["date"], rows[-1]["date"], len(rows), years))
print("谷底分均值 %.0f；价格低于 20 日线的天数 %d（平均 %.1f%%）" % (
    sum(r["score"] for r in rows) / len(rows),
    sum(1 for r in rows if r["gap"] > 0), sum(max(0, r["gap"]) for r in rows) / len(rows)))


def cur(s):
    if s <= 50:
        return 100
    if s >= 80:
        return 500
    return int(round((100 + (s - 50) / 30.0 * 400) / 10.0) * 10)


def tier(s, extra_on=False):
    if s < 20:
        return 50
    if s < 75:
        return 100
    return 500


def tier_c(r):
    base = 500 if r["score"] >= 75 else (50 if r["score"] < 20 else 100)
    extra = 0.0
    if r["score"] >= 75 and r["gap"] > 3:
        extra = (r["gap"] - 3) / 1.0 * 500        # 每多 1 个百分点加 500
        r["extra"] = extra
    else:
        r["extra"] = 0.0
    return base + extra


for name, fn in (("A 现行（100–500 线性）", lambda r: cur(r["score"])),
                 ("B 分档 50/100/500", lambda r: tier(r["score"])),
                 ("C 分档 + 深度加码", tier_c)):
    for r in rows:
        r.pop("extra", None)
    s = simulate(rows, fn)
    print("\n【%s】" % name)
    print("  投入 ¥%s（日均 ¥%.0f，年均 ¥%s）" % (
        format(int(s["invested"]), ","), s["invested"] / len(rows),
        format(int(s["invested"] / years), ",")))
    print("  市值 ¥%s  盈亏 %+.2f%%  XIRR %+.2f%%  最大回撤 %.2f%%  手续费 ¥%.0f" % (
        format(int(s["value"]), ","), s["ret"] * 100, s["xirr"] * 100, s["mdd"] * 100, s["fees"]))
    print("  分年投入: %s" % " ".join("%s ¥%s" % (k, format(int(v), ",")) for k, v in sorted(s["per_year"].items())))
    if name.startswith("C"):
        print("  加码部分共 ¥%s，触发 %d 天（占 %.0f%%），单日最高 ¥%s" % (
            format(int(s["extra_total"]), ","), s["extra_days"],
            100.0 * s["extra_days"] / len(rows),
            format(int(max((500 + (r["gap"] - 3) * 500) for r in rows if r["score"] >= 75 and r["gap"] > 3)), ",")
            if s["extra_days"] else "—"))
