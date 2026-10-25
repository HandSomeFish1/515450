# -*- coding: utf-8 -*-
"""最终方案：利差的滚动分位（不同窗口对比）"""
import math
import statistics as st

import daily_score as ds
import dca_core as bt

nav, adj = bt.fetch_fund_nav()
pe = ds.fetch_valuation_history("CSIH30269")
bond = ds.fetch_cn10y()
val = ds.fetch_index_valuation("CSIH30269")
payout = val["div"] / 100.0 * val["pe"]
pe_d = {d: p for d, p in pe}
pe_dates = sorted(pe_d)
bond_d = {d: v for d, v in bond}
bond_dates = sorted(bond_d)


def asof(dates, m, d):
    if d < dates[0]:
        return None
    lo, hi = 0, len(dates) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if dates[mid] <= d:
            lo = mid
        else:
            hi = mid - 1
    return m[dates[lo]]


D = [d for d, _ in adj]
P = [p for _, p in adj]
N = len(D)

spread = []
for i in range(N):
    pj = asof(pe_dates, pe_d, D[i])
    yj = asof(bond_dates, bond_d, D[i])
    spread.append(100.0 * payout / pj - yj if pj and yj else None)


def ranks(x):
    o = sorted(range(len(x)), key=lambda i: x[i])
    r = [0] * len(x)
    for p, i in enumerate(o):
        r[i] = p + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else 0.0


def build(win, min_win):
    rows = []
    for i in range(min_win + 60, N):
        if spread[i] is None:
            continue
        w = [spread[j] for j in range(i - win + 1, i + 1) if spread[j] is not None]
        if len(w) < min_win:
            continue
        rows.append((D[i], P[i], 100.0 * sum(1 for x in w if x <= spread[i]) / len(w), spread[i]))
    return rows


for win in (250, 500, 750):
    rows = build(win, min(win, 200))
    ds_ = [r[0] for r in rows]
    ps = [r[1] for r in rows]
    sc = [r[2] for r in rows]
    n = len(rows)
    i23 = next(i for i, d in enumerate(ds_) if d >= "2023-01")
    cross = sum(1 for i in range(1, n) if (sc[i - 1] - 50) * (sc[i] - 50) < 0)
    print("\n=== 利差滚动分位，窗口 %d 天 === %s ~ %s（%d 天）穿50 %d 次" % (
        win, ds_[0], ds_[-1], n, cross))
    for label, a, b in (("全样本", 0, n - 61), ("2021-22", 0, min(i23, n - 61)), ("2023-26", i23, n - 61)):
        if b - a < 120:
            continue
        idx = list(range(a, b))
        rho = spearman([sc[i] for i in idx], [ps[i + 60] / ps[i] - 1 for i in idx])
        s = sorted(sc[i] for i in idx)
        hi = [ps[i + 60] / ps[i] - 1 for i in idx if sc[i] >= s[int(len(s) * 0.8)]]
        lo = [ps[i + 60] / ps[i] - 1 for i in idx if sc[i] <= s[int(len(s) * 0.2)]]
        print("  %-8s ρ%+.2f  最高20%% %+.2f%%  最低20%% %+.2f%%  >80 占 %.0f%%" % (
            label, rho, st.mean(hi) * 100, st.mean(lo) * 100,
            100.0 * sum(1 for i in idx if sc[i] > 80) / len(idx)))

# 选 500 天窗口输出
rows = build(250, 200)
import json
json.dump([[r[0], round(r[1], 4), round(r[2], 1)] for r in rows],
          open("score_series.json", "w", encoding="utf-8"), ensure_ascii=False)
print("\n已写入 score_series.json（%d 天）" % len(rows))
print("窗口 250，最后一天分数", rows[-1][2])
