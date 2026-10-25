# -*- coding: utf-8 -*-
"""换思路：用“超卖 + 转折确认”做谷底分，分牛熊两段验证"""
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

rsi = [None] * N
ag = al = 0.0
for i in range(1, N):
    ch = P[i] - P[i - 1]
    if i == 14:
        ag = sum(max(P[j] - P[j - 1], 0) for j in range(1, 15)) / 14
        al = sum(max(-(P[j] - P[j - 1]), 0) for j in range(1, 15)) / 14
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


feat = []
for i in range(300, N):
    d, p = D[i], P[i]
    ma5 = sum(P[i - 4:i + 1]) / 5
    ma20 = sum(P[i - 19:i + 1]) / 20
    ma60 = sum(P[i - 59:i + 1]) / 60
    d5 = ma5 / (sum(P[i - 9:i - 4]) / 5) - 1            # MA5 斜率
    dd60 = p / max(P[i - 59:i + 1]) - 1                  # 距 60 日高点
    dist20 = p / ma20 - 1
    r = rsi[i]
    r_pct = rank([x for x in rsi[i - 249:i + 1] if x is not None], r)
    dd_pct = rank([P[j] / max(P[max(0, j - 59):j + 1]) - 1 for j in range(i - 249, i + 1)], dd60)
    d20_pct = rank([P[j] / (sum(P[j - 19:j + 1]) / 20) - 1 for j in range(i - 250, i + 1)], dist20)
    pe_now = asof(pe_dates, pe_d, d)
    y10 = asof(bond_dates, bond_d, d)
    spread = (100.0 * payout / pe_now - y10) if pe_now and y10 is not None else None
    sp_pct = None
    if spread is not None:
        hist = []
        for j in range(i - 499, i + 1):
            pj = asof(pe_dates, pe_d, D[j])
            yj = asof(bond_dates, bond_d, D[j])
            if pj and yj:
                hist.append(100.0 * payout / pj - yj)
        sp_pct = rank(hist, spread)
    turn = 1.0 if (d5 > 0 and p > ma5) else 0.0
    feat.append(dict(d=d, p=p, rsi=r, r_pct=r_pct, dd60=dd60, dd_pct=dd_pct,
                     dist20=dist20, d20_pct=d20_pct, sp_pct=sp_pct, turn=turn,
                     ma60=ma60))

print("样本 %s ~ %s，%d 天" % (feat[0]["d"], feat[-1]["d"], len(feat)))


def ev(name, key, top=0.15):
    vals = [(f[key], i) for i, f in enumerate(feat) if key and f.get(key) is not None]
    xs = [v for v, _ in vals]
    thr = sorted(xs)[int(len(xs) * (1 - top))]
    segs = {"全样本": (0, len(feat)), "2021-22": (0, 0), "2023-26": (0, 0)}
    out = []
    for seg, (a, b) in segs.items():
        if seg == "2021-22":
            a = next(i for i, f in enumerate(feat) if f["d"] >= "2021-02")
            b = next(i for i, f in enumerate(feat) if f["d"] > "2022-12-31")
        elif seg == "2023-26":
            a = next(i for i, f in enumerate(feat) if f["d"] >= "2023-01")
            b = len(feat)
        idx = [i for i in range(a, min(b, len(feat) - 60))]
        if len(idx) < 100:
            out.append("%s: n/a" % seg)
            continue
        sp = spearman([feat[i][key] for i in idx], [feat[i + 60]["p"] / feat[i]["p"] - 1 for i in idx])
        hi = [i for i in idx if feat[i][key] >= thr]
        r60 = [feat[i + 60]["p"] / feat[i]["p"] - 1 for i in hi]
        lo_ = [i for i in idx if feat[i][key] <= sorted(xs)[int(len(xs) * 0.15)]]
        rl = [feat[i + 60]["p"] / feat[i]["p"] - 1 for i in lo_]
        out.append("%s: ρ%+.2f 高分均值%+.2f%%(n=%d) 低分%+.2f%%" % (
            seg, sp, st.mean(r60) * 100 if r60 else 0, len(r60),
            st.mean(rl) * 100 if rl else 0))
    print("%-22s %s" % (name, " | ".join(out)))


ev("RSI 反向", "r_pct")
ev("距 60 日高点(反)", "dd_pct")
ev("距 20 日线(反)", "d20_pct")
ev("利差分位", "sp_pct")
ev("转折(MA5向上)", "turn")
