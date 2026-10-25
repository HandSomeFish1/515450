# -*- coding: utf-8 -*-
"""谷底分：便宜度 = 0.60×回撤深度 + 0.25×三年位置 + 0.15×利差位置，
   再取过去 750 个交易日的分位（0-100，越高越接近谷底）。"""
import statistics as st

BANDS = [(0, 20, "#ef4444", "顶部区"), (20, 40, "#f97316", "偏热"),
         (40, 60, "#94a3b8", "中性"), (60, 80, "#4ade80", "偏冷"),
         (80, 100, "#22c55e", "谷底区")]


def band(v):
    for a, b, c, name in BANDS:
        if v < b or b == 100:
            return a, b, c, name
    return BANDS[-1]


def band_action(v):
    """分数越高越接近谷底 → 越该买。"""
    if v >= 80:
        return ("#22c55e", "rgba(34,197,94,.16)", "谷底区：重点加仓 5-6 成",
                "回撤够深、位置够低，历史上这段后 60 日平均 +7.5%。")
    if v >= 60:
        return ("#4ade80", "rgba(74,222,128,.16)", "偏冷：分批加仓 3-4 成",
                "已经跌出空间，可以小步加，留一半给更深的谷底。")
    if v >= 40:
        return ("#94a3b8", "rgba(148,163,184,.16)", "中性：按常规节奏定投",
                "不深不浅，按 100–500 的规则正常投即可。")
    if v >= 20:
        return ("#f59e0b", "rgba(245,158,11,.16)", "偏热：减少投入 1-2 成",
                "离一年高点还近，跌得不够，少买一点。")
    return ("#ef4444", "rgba(239,68,68,.16)", "顶部区：暂停买入",
            "在高位附近，等回撤 10% 以上再考虑加仓。")


def rank(seq, v):
    return sum(1 for x in seq if x <= v) / float(len(seq)) if seq else 0.5


def build(frames, window=750):
    adj = frames["nav_adj"]
    pe = dict(frames["pe"])
    bond = dict(frames["bond"])
    val = frames["val"]
    payout = val["div"] / 100.0 * val["pe"]

    dates = [d for d, _ in adj]
    px = [p for _, p in adj]
    n = len(dates)

    pe_dates = sorted(pe)
    bond_dates = sorted(bond)

    def asof(ds_, m, d):
        lo, hi = 0, len(ds_) - 1
        if d < ds_[0]:
            return None
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if ds_[mid] <= d:
                lo = mid
            else:
                hi = mid - 1
        return m[ds_[lo]]

    spread = []
    for d in dates:
        p = asof(pe_dates, pe, d)
        y = asof(bond_dates, bond, d)
        spread.append(100.0 * payout / p - y if p and y is not None else None)

    rows = []
    for i in range(window, n):
        if spread[i] is None:
            continue
        A = 100 * (1 - rank(px[i - window + 1:i + 1], px[i]))
        hi250 = max(px[i - 249:i + 1])
        D = 100 * min(1.0, abs(px[i] / hi250 - 1) / 0.15)
        hist = [s for s in spread[i - window + 1:i + 1] if s is not None]
        E = 100 * rank(hist, spread[i])
        rows.append(dict(date=dates[i], price=px[i], A=A, D=D, E=E,
                         raw=0.60 * D + 0.25 * A + 0.15 * E))

    raws = [r["raw"] for r in rows]
    for i, r in enumerate(rows):
        w = raws[max(0, i - window + 1):i + 1]
        r["score"] = 100.0 * sum(1 for x in w if x <= r["raw"]) / len(w)
    return rows


def summary(rows):
    last = rows[-1]
    a, b, c, name = band(last["score"])
    prev = rows[-21] if len(rows) > 21 else rows[0]
    return dict(score=round(last["score"]), band=name, color=c, lo=a, hi=b,
                D=last["D"], A=last["A"], E=last["E"],
                prev20=round(prev["score"]), date=last["date"])
