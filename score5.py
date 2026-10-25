# -*- coding: utf-8 -*-
"""谷底分 v3：按市场状态动态换权重"""
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


rows = []
for i in range(300, N):
    d, p = D[i], P[i]
    ma20 = sum(P[i - 19:i + 1]) / 20
    ma60 = sum(P[i - 59:i + 1]) / 60
    ma120 = sum(P[i - 119:i + 1]) / 120
    ma250 = sum(P[i - 249:i + 1]) / 250
    slope250 = ma250 / (sum(P[i - 309:i - 59]) / 250) - 1 if i >= 310 else 0
    hi250 = max(P[i - 249:i + 1])
    DD = 100 * min(1.0, abs(p / hi250 - 1) / 0.15)
    POS = 100 * (1 - rank(P[i - 249:i + 1], p))
    # 企稳信号（0-100，5 日平滑）
    raw_turn = []
    for k in range(i - 4, i + 1):
        s = 0
        s += 30 if P[k] > sum(P[k - 19:k + 1]) / 20 else 0
        s += 25 if (sum(P[k - 4:k + 1]) / 5) > (sum(P[k - 9:k - 4]) / 5) else 0
        s += 25 if (rsi[k] or 0) > 45 else 0
        s += 20 if P[k] > sum(P[k - 9:k + 1]) / 10 else 0
        raw_turn.append(s)
    TURN = sum(raw_turn) / 5.0
    pe_now = asof(pe_dates, pe_d, d)
    y10 = asof(bond_dates, bond_d, d)
    if not pe_now or y10 is None:
        continue
    spread = 100.0 * payout / pe_now - y10
    hist = []
    for j in range(i - 499, i + 1):
        pj = asof(pe_dates, pe_d, D[j])
        yj = asof(bond_dates, bond_d, D[j])
        if pj and yj:
            hist.append(100.0 * payout / pj - yj)
    SP = 100 * rank(hist, spread)
    # 状态：0=阴跌，1=震荡，2=上涨
    if ma120 < ma250 and p < ma250:
        regime = 0
    elif ma120 > ma250 and p > ma250:
        regime = 2
    else:
        regime = 1
    if regime == 0:        # 阴跌：不奖励“跌得深”，奖励“企稳 + 便宜”
        score = 0.50 * SP + 0.50 * TURN
    elif regime == 2:      # 上涨：跌深了就是机会
        score = 0.40 * SP + 0.40 * DD + 0.20 * POS
    else:                  # 震荡：三个都看
        score = 0.40 * SP + 0.30 * DD + 0.30 * TURN
    rows.append(dict(d=d, p=p, score=score, SP=SP, DD=DD, POS=POS, TURN=TURN, regime=regime))

ds_ = [r["d"] for r in rows]
ps = [r["p"] for r in rows]
sc = [r["score"] for r in rows]
n = len(rows)
print("样本 %s ~ %s，%d 天" % (ds_[0], ds_[-1], n))
from collections import Counter
print("状态分布：", dict(Counter(r["regime"] for r in rows)), "（0=阴跌 1=震荡 2=上涨）")

i23 = next(i for i, d in enumerate(ds_) if d >= "2023-01")
for label, a, b in (("全样本", 0, n - 61), ("2021-22", 0, min(i23, n - 61)), ("2023-26", i23, n - 61)):
    idx = list(range(a, b))
    rho = spearman([sc[i] for i in idx], [ps[i + 60] / ps[i] - 1 for i in idx])
    s = sorted(sc[i] for i in idx)
    hi = [ps[i + 60] / ps[i] - 1 for i in idx if sc[i] >= s[int(len(s) * 0.8)]]
    lo = [ps[i + 60] / ps[i] - 1 for i in idx if sc[i] <= s[int(len(s) * 0.2)]]
    print("%-8s ρ%+.2f  最高20%% %+.2f%%  最低20%% %+.2f%%  >80 占 %.0f%%" % (
        label, rho, st.mean(hi) * 100, st.mean(lo) * 100,
        100.0 * sum(1 for i in idx if sc[i] > 80) / len(idx)))

# 阴跌段里，分数是否避开“一路下跌”的日子
bear = [i for i in range(0, n - 61) if rows[i]["regime"] == 0]
if bear:
    hi_b = [ps[i + 60] / ps[i] - 1 for i in bear if sc[i] > 80]
    lo_b = [ps[i + 60] / ps[i] - 1 for i in bear if sc[i] < 40]
    print("阴跌日共 %d 天：高分后60日 %+.2f%%（n=%d），低分 %+.2f%%（n=%d）" % (
        len(bear), st.mean(hi_b) * 100 if hi_b else 0, len(hi_b),
        st.mean(lo_b) * 100 if lo_b else 0, len(lo_b)))
    print("  阴跌日里 >80 的天数：%d（%.0f%%）" % (
        sum(1 for i in bear if sc[i] > 80), 100.0 * sum(1 for i in bear if sc[i] > 80) / len(bear)))

print("最新：%s 分数 %.0f（状态 %d）" % (ds_[-1], sc[-1], rows[-1]["regime"]))

import json
json.dump([[r["d"], round(r["p"], 4), round(r["score"], 1)] for r in rows],
          open("score_series.json", "w", encoding="utf-8"), ensure_ascii=False)
print("已写入 score_series.json（%d 天）" % len(rows))
