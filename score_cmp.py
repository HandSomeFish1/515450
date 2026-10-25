# -*- coding: utf-8 -*-
"""对比不同回看窗口：谷底分在 2021-2022 熊市里能不能分出低谷和山峰"""
import math
import statistics as st
import sys

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


dates_all = [d for d, _ in adj]
px_all = [p for _, p in adj]
N = len(dates_all)

rsi = [None] * N
ag = al = 0.0
for i in range(1, N):
    ch = px_all[i] - px_all[i - 1]
    if i == 14:
        ag = sum(max(px_all[j] - px_all[j - 1], 0) for j in range(1, 15)) / 14
        al = sum(max(-(px_all[j] - px_all[j - 1]), 0) for j in range(1, 15)) / 14
        rsi[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    elif i > 14:
        ag = (ag * 13 + max(ch, 0)) / 14
        al = (al * 13 + max(-ch, 0)) / 14
        rsi[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def rank(seq, v):
    return sum(1 for x in seq if x <= v) / float(len(seq)) if seq else 0.5


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


def build(L, min_win=120):
    rows = []
    for i in range(min_win, N):
        d, p = dates_all[i], px_all[i]
        A = 100 * (1 - rank(px_all[max(0, i - L + 1):i + 1], p))
        hi250 = max(px_all[max(0, i - 249):i + 1])
        D = 100 * min(1.0, abs(p / hi250 - 1) / 0.15)
        pe_now = asof(pe_dates, pe_d, d)
        y10 = asof(bond_dates, bond_d, d)
        if not pe_now or y10 is None:
            continue
        spread = 100.0 * payout / pe_now - y10
        sp_hist = []
        for j in range(max(0, i - L + 1), i + 1):
            pj = asof(pe_dates, pe_d, dates_all[j])
            yj = asof(bond_dates, bond_d, dates_all[j])
            if pj and yj:
                sp_hist.append(100.0 * payout / pj - yj)
        E = 100 * rank(sp_hist, spread)
        rows.append((d, p, 0.60 * D + 0.25 * A + 0.15 * E))
    raw = [r[2] for r in rows]
    sc = []
    for i in range(len(raw)):
        w = raw[max(0, i - L + 1):i + 1]
        if len(w) < min_win:
            sc.append(None)
            continue
        sc.append(100.0 * sum(1 for x in w if x <= raw[i]) / len(w))
    keep = [i for i, v in enumerate(sc) if v is not None]
    rows = [rows[i] for i in keep]
    sc = [sc[i] for i in keep]
    return rows, sc


for L in (250, 500, 750):
    rows, sc = build(L)
    ds_ = [r[0] for r in rows]
    ps = [r[1] for r in rows]
    n = len(rows)
    print("\n=== 回看窗口 %d 天 ===  %s ~ %s（%d 天）" % (L, ds_[0], ds_[-1], n))
    cross = sum(1 for i in range(1, n) if (sc[i - 1] - 50) * (sc[i] - 50) < 0)
    c60 = spearman([sc[i] for i in range(n - 60)], [ps[i + 60] / ps[i] - 1 for i in range(n - 60)])
    print("  穿50 %d 次，均值 %.0f，前60日 Spearman %+.3f" % (cross, st.mean(sc), c60))
    # 2021-2022 段
    seg = [i for i in range(n) if "2021-01-01" <= ds_[i] <= "2022-12-31"]
    if seg:
        s2 = [sc[i] for i in seg]
        p2 = [ps[i] for i in seg]
        c2 = sum(1 for k in range(1, len(s2)) if (s2[k - 1] - 50) * (s2[k] - 50) < 0)
        idx = [i for i in seg if i + 60 < n]
        sp2 = spearman([sc[i] for i in idx], [ps[i + 60] / ps[i] - 1 for i in idx])
        print("  2021-2022：%d 天，穿50 %d 次，区间 %.0f~%.0f，前60日 Spearman %+.3f" % (
            len(seg), c2, min(s2), max(s2), sp2))
        for lo, hi in ((80, 101), (60, 80), (0, 60)):
            ss = [i for i in idx if lo <= sc[i] < hi]
            if ss:
                rr = [ps[i + 60] / ps[i] - 1 for i in ss]
                print("    分 %3d-%3d：%3d 天，后60日均 %+.2f%%，正收益 %.0f%%" % (
                    lo, hi - 1, len(ss), st.mean(rr) * 100, 100 * sum(1 for x in rr if x > 0) / len(rr)))
