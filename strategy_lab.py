#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
515450 温度分定投 —— 策略实验室（成立以来回测）

在 100~500 元/天的约束下，搜索「温度分 → 当日金额」的映射规则，
用 515450 成立以来的真实净值数据（2020-01 成立，前 250 个交易日用于年线预热，
实际回测从 2021-01 起）逐日回测，并按年份拆分检验稳定性。

输出：strategy_2026.html、strategy_2026.csv
"""

import csv
import datetime as dt
import json
import math
import os
import sys

import dca_core as bt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LO, HI = 100.0, 500.0           # 每日金额下限 / 上限
ROUND = 10.0                    # 取整到 10 元


# --------------------------------------------------------------------------
# 规则族（输入温度分，输出当日金额）
# --------------------------------------------------------------------------

def linear_T(T):
    return lambda s: LO + max(0.0, min(1.0, (T - s) / float(T))) * (HI - LO)


def anchors(a_hi_score, a_lo_score):
    """a_hi_score 分 → 上限，a_lo_score 分 → 下限，中间线性。"""
    return lambda s: LO + max(0.0, min(1.0, (a_lo_score - s) / float(a_lo_score - a_hi_score))) * (HI - LO)


def power(k):
    return lambda s: LO + ((100.0 - s) / 100.0) ** k * (HI - LO)


def sigmoid(c, w):
    return lambda s: LO + (1.0 / (1.0 + math.exp(-(c - s) / float(w)))) * (HI - LO)


def tiers(bands):
    def f(s):
        for i, t in enumerate(bands):
            if s <= t:
                return LO + (HI - LO) * (len(bands) - i) / float(len(bands))
        return LO
    return f


def families():
    out = []
    hi, lo = int(HI), int(LO)
    for T in (50, 60, 70, 80, 90, 100):
        out.append(("linear%d" % T, "线性 T=%d" % T,
                    "金额 = %d + (%d − 分) × %.1f" % (lo, T, (hi - lo) / float(T)), linear_T(T)))
    for a, b in ((10, 55), (15, 55), (15, 60), (20, 60), (20, 65), (25, 65), (25, 70), (30, 75)):
        out.append(("anchor%d_%d" % (a, b), "锚点 %d→%d / %d→%d" % (a, hi, b, lo),
                    "%d 分投 %d 元，%d 分投 %d 元，中间线性" % (a, hi, b, lo), anchors(a, b)))
    for k in (0.6, 1.0, 1.6, 2.0):
        out.append(("pow%.1f" % k, "幂函数 k=%.1f" % k,
                    "金额 = %d + ((100 − 分)/100)^%.1f × %d" % (lo, k, hi - lo), power(k)))
    for c, w in ((40, 15), (50, 10), (50, 20)):
        out.append(("sig%d_%d" % (c, w), "S 曲线 c=%d w=%d" % (c, w),
                    "逻辑斯蒂映射，中点在 %d 分" % c, sigmoid(c, w)))
    for bands in ((20, 40, 60, 80), (30, 50, 70, 85)):
        out.append(("tier%s" % "".join(map(str, bands)), "档位 %s" % "/".join(map(str, bands)),
                    "按分数段跳档", tiers(bands)))
    out.append(("flatmid", "等额定投 %d" % ((hi + lo) // 2),
                "每天固定 %d 元" % ((hi + lo) // 2), lambda s: (hi + lo) / 2.0))
    out.append(("flatmax", "满额定投 %d" % hi, "每天固定 %d 元" % hi, lambda s: float(hi)))
    return out


# --------------------------------------------------------------------------
# 回测
# --------------------------------------------------------------------------

def sim(dates, fn, fee=0.0):
    invested = shares = 0.0
    cash = []
    worst = 0.0
    n = 0
    for d, price, score in dates:
        amt = max(LO, min(HI, bt.round_to(fn(score), ROUND)))
        shares += amt / (1.0 + fee) / price
        invested += amt
        cash.append((dt.date.fromisoformat(d), -float(amt)))
        n += 1
        worst = min(worst, shares * price / invested - 1.0)
    last_d, last_px, _ = dates[-1]
    value = shares * last_px
    cash.append((dt.date.fromisoformat(last_d), value))
    return {
        "invested": invested, "value": value, "n": n,
        "ret": value / invested - 1.0 if invested else 0.0,
        "xirr": bt.xirr(cash), "dd": worst,
        "cost": invested / shares if shares else 0.0,
        "avg": invested / n if n else 0.0,
    }


def lump(dates, total, fee=0.0):
    d0, p0, _ = dates[0]
    d1, p1, _ = dates[-1]
    shares = total / (1.0 + fee) / p0
    cash = [(dt.date.fromisoformat(d0), -float(total)),
            (dt.date.fromisoformat(d1), shares * p1)]
    return {"invested": total, "value": shares * p1,
            "ret": p1 / p0 - 1.0, "xirr": bt.xirr(cash),
            "cost": p0, "n": 1, "avg": total}


# --------------------------------------------------------------------------
# 图表
# --------------------------------------------------------------------------

def chart(curve, height=250):
    if not curve:
        return ""
    w, h, pl, pr, pt, pb = 820, height, 60, 16, 18, 34
    n = len(curve)
    maxv = max(max(c["invested"] for c in curve), max(c["value"] for c in curve)) * 1.08 or 1

    def x(i):
        return pl + i * (w - pl - pr) / float(max(n - 1, 1))

    def y(v):
        return h - pb - v / maxv * (h - pt - pb)

    inv = " ".join("%.1f,%.1f" % (x(i), y(c["invested"])) for i, c in enumerate(curve))
    val = " ".join("%.1f,%.1f" % (x(i), y(c["value"])) for i, c in enumerate(curve))
    area = "%.1f,%.1f " % (x(0), h - pb) + val + " %.1f,%.1f" % (x(n - 1), h - pb)

    grid, labels = [], []
    for k in range(5):
        v = maxv * k / 4.0
        yy = y(v)
        grid.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#1e2b44"/>' % (pl, yy, w - pr, yy))
        grid.append('<text x="%d" y="%.1f" fill="#6b7d98" font-size="10" text-anchor="end">%d</text>'
                    % (pl - 8, yy + 3, round(v)))
    for i in range(0, n, max(1, n // 7)):
        labels.append('<text x="%.1f" y="%d" fill="#6b7d98" font-size="10" text-anchor="middle">%s</text>'
                      % (x(i), h - pb + 18, curve[i]["date"][:7]))

    return (
        '<svg class="chart" viewBox="0 0 %d %d">' % (w, h) + "".join(grid) +
        '<defs><linearGradient id="gv" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%%" stop-color="#22c55e" stop-opacity=".28"/>'
        '<stop offset="100%%" stop-color="#22c55e" stop-opacity="0"/></linearGradient></defs>' +
        '<polygon points="%s" fill="url(#gv)"/>' % area +
        '<polyline points="%s" fill="none" stroke="#22c55e" stroke-width="2.2"/>' % val +
        '<polyline points="%s" fill="none" stroke="#94a3b8" stroke-width="1.4" stroke-dasharray="5 4"/>' % inv +
        "".join(labels) +
        '<text x="%d" y="%d" fill="#22c55e" font-size="11">持仓市值</text>' % (pl + 6, pt + 10) +
        '<text x="%d" y="%d" fill="#94a3b8" font-size="11">累计投入</text>' % (pl + 6, pt + 26) +
        "</svg>")


def amount_table(fn):
    return [(s, max(LO, min(HI, bt.round_to(fn(s), ROUND)))) for s in range(0, 101, 5)]


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------

def pct(x, digits=2):
    return ("%+." + str(digits) + "f%%") % (x * 100.0)


def irrs(x):
    return ("%.2f%%" % (x * 100.0)) if x is not None else "—"


def main():
    with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
        cfg = json.load(f)

    rows = bt.build_daily_scores(cfg)
    if not rows:
        print("历史数据不足")
        return 1
    pts = [(r["date"], r["price"], r["score"]) for r in rows]
    years = sorted({p[0][:4] for p in pts})
    fee = float((cfg.get("dca") or {}).get("fee_rate", 0.0))
    flat = lambda s: (HI + LO) / 2.0
    flat_all = sim(pts, flat, fee)
    flat_year = {y: sim([p for p in pts if p[0][:4] == y], flat, fee) for y in years}

    results = []
    for key, label, desc, fn in families():
        a = sim(pts, fn, fee)
        per = {y: sim([p for p in pts if p[0][:4] == y], fn, fee) for y in years}
        wins = sum(1 for y in years if (per[y]["xirr"] or -9) > (flat_year[y]["xirr"] or -9))
        results.append({"key": key, "label": label, "desc": desc, "fn": fn,
                        "all": a, "years": per, "wins": wins})

    champ = max(results, key=lambda r: r["all"]["xirr"] or -9)
    pool = [r for r in results
            if r["all"]["avg"] >= LO * 1.5 and r["key"] not in ("flatmid", "flatmax")]
    best = max(pool, key=lambda r: r["all"]["xirr"] or -9) if pool else champ

    cur = best["all"]
    lump_all = lump(pts, cur["invested"], fee)

    results.sort(key=lambda r: -(r["all"]["xirr"] or -9))
    top = results[:12]

    def rank_rows(items):
        out = ""
        for i, r in enumerate(items, 1):
            tag = ""
            if r is best:
                tag = ' <span class="tag">推荐</span>'
            elif r is champ:
                tag = ' <span class="tag tag-warn">XIRR 最高</span>'
            out += (
                '<tr><td class="num">%d</td><td>%s%s<div class="sub2">%s</div></td>'
                '<td class="num">%s</td><td class="num strong">%s</td>'
                '<td class="num">%s</td><td class="num">%s</td><td class="num">%d/%d</td></tr>' % (
                    i, r["label"], tag, r["desc"], "%d" % r["all"]["avg"],
                    irrs(r["all"]["xirr"]), pct(r["all"]["dd"]),
                    irrs(r["years"].get("2022", {}).get("xirr")),
                    r["wins"], len(years)))
        return out

    year_rows = ""
    for y in years:
        a = best["years"][y]
        f = flat_year[y]
        diff = (a["xirr"] or 0) - (f["xirr"] or 0)
        year_rows += ('<tr><td>%s</td><td class="num strong">%s</td><td class="num">%s</td>'
                      '<td class="num %s">%+.2f pp</td><td class="num">%d</td></tr>' % (
                          y, irrs(a["xirr"]), irrs(f["xirr"]),
                          "up" if diff > 0 else "down", diff * 100, a["n"]))

    picks = pts
    shares = invested = 0.0
    rows_html, curve = [], []
    for d, price, score in picks:
        amt = max(LO, min(HI, bt.round_to(best["fn"](score), ROUND)))
        shares += amt / price
        invested += amt
        curve.append({"date": d, "invested": invested, "value": shares * price, "amount": amt})
        rows_html.append(
            '<tr><td>%s</td><td class="num">%d</td><td class="num strong">%d</td>'
            '<td class="num">%.3f</td><td class="num">%.2f</td>'
            '<td class="num">%s</td><td class="num" style="color:%s">%s</td></tr>' % (
                d, score, amt, price, amt / price, format(int(invested), ","),
                "#22c55e" if shares * price >= invested else "#ef4444",
                format(int(round(shares * price)), ",")))
    detail_html = "".join(rows_html[-12:])

    tbl = "".join('<tr><td class="num">%d</td><td class="num strong">%d 元</td></tr>' % (s, a)
                  for s, a in amount_table(best["fn"]))

    sens = ""
    for key in ("anchor15_60", "anchor20_60", "anchor20_65", "anchor25_65",
                "anchor25_70", "anchor30_75"):
        r = [x for x in results if x["key"] == key][0]
        sens += ('<tr><td>%s</td><td class="num">%s</td><td class="num">%d</td>'
                 '<td class="num">%s</td></tr>' % (
                     r["label"], irrs(r["all"]["xirr"]), r["all"]["avg"],
                     irrs(r["years"].get("2022", {}).get("xirr"))))

    xs = [r["all"]["xirr"] or 0 for r in results]
    ys = [sum((r["years"][y]["xirr"] or 0) for y in years) / len(years) for r in results]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
    corr = num / den if den else 0.0

    if champ is best:
        champ_note = ("推荐规则同时是全区间 XIRR 第一名：<b>%s</b>，均投 %d 元/天、XIRR %s。"
                      % (champ["label"], champ["all"]["avg"], irrs(champ["all"]["xirr"])))
    else:
        champ_note = ("全区间 XIRR 最高的是 <b>%s</b>（均投 %d 元/天，XIRR %s），但它长期压着 100 元下限、"
                      "资金利用率低；推荐规则在保持第一梯队的同时把均投拉到 %d 元/天，"
                      "且在 %d/%d 个年份跑赢等额日投。" % (
                          champ["label"], champ["all"]["avg"], irrs(champ["all"]["xirr"]),
                          cur["avg"], best["wins"], len(years)))

    with open(os.path.join(BASE_DIR, "strategy_template.html"), "r", encoding="utf-8") as f:
        tpl = f.read()

    rep = {
        "__RULE__": best["label"], "__RULE_DESC__": best["desc"],
        "__Y26_XIRR__": irrs(cur["xirr"]),
        "__INV__": format(int(cur["invested"]), ","),
        "__VAL__": format(int(round(cur["value"])), ","),
        "__PROFIT__": format(int(round(cur["value"] - cur["invested"])), ","),
        "__RET__": pct(cur["ret"]), "__DD__": pct(cur["dd"]),
        "__AVGAMT__": "%d" % cur["avg"], "__N__": str(cur["n"]),
        "__YEARLY__": format(int(round(cur["invested"] / max(
            (dt.date.fromisoformat(pts[-1][0]) - dt.date.fromisoformat(pts[0][0])).days / 365.0, 1))), ","),
        "__DETAILN__": str(min(12, cur["n"])),
        "__COST__": "%.3f" % cur["cost"], "__LASTPX__": "%.3f" % pts[-1][1],
        "__CHAMPNOTE__": champ_note,
        "__FLAT_XIRR__": irrs(flat_all["xirr"]),
        "__FLAT_INV__": format(int(flat_all["invested"]), ","),
        "__FLAT_VAL__": format(int(round(flat_all["value"])), ","),
        "__FULL_XIRR__": irrs([r for r in results if r["key"] == "flatmax"][0]["all"]["xirr"]),
        "__FULL_INV__": format(int([r for r in results if r["key"] == "flatmax"][0]["all"]["invested"]), ","),
        "__FULL_VAL__": format(int(round([r for r in results if r["key"] == "flatmax"][0]["all"]["value"])), ","),
        "__FLATAMT__": "%d" % ((HI + LO) / 2),
        "__FULLAMT__": "%d" % HI,
        "__LOAMT__": "%d" % LO,
        "__HIAMT__": "%d" % HI,
        "__LUMP_XIRR__": irrs(lump_all["xirr"]), "__LUMP_RET__": pct(lump_all["ret"]),
        "__LUMP_VAL__": format(int(round(lump_all["value"])), ","),
        "__TBL__": tbl, "__DETAIL__": detail_html, "__CHART__": chart(curve),
        "__TOP__": rank_rows(top), "__SENS__": sens, "__YEARROWS__": year_rows,
        "__CORR__": "%.2f" % corr, "__NRULES__": str(len(results)),
        "__SPAN26__": "%s ~ %s" % (pts[0][0], pts[-1][0]),
        "__WINY__": "%d/%d" % (best["wins"], len(years)),
        "__FEE__": "%.2f%%" % (fee * 100),
    }
    for k, v in rep.items():
        tpl = tpl.replace(k, v)

    with open(os.path.join(BASE_DIR, "strategy_2026.html"), "w", encoding="utf-8") as f:
        f.write(tpl)

    with open(os.path.join(BASE_DIR, "strategy_2026.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["日期", "温度分", "投入", "复权净值", "份额", "累计投入", "累计市值"])
        shares = invested = 0.0
        for d, price, score in pts:
            amt = max(LO, min(HI, bt.round_to(best["fn"](score), ROUND)))
            shares += amt / price
            invested += amt
            w.writerow([d, score, amt, "%.4f" % price, "%.2f" % (amt / price),
                        "%.0f" % invested, "%.0f" % (shares * price)])

    print("[推荐] %s（日投，每笔 %d~%d 元）" % (best["label"], LO, HI))
    print("  区间 %s ~ %s，%d 个交易日" % (pts[0][0], pts[-1][0], len(pts)))
    print("  投入 %d，市值 %d，收益 %s，XIRR %s，最大浮亏 %s，均投 %d 元/天" % (
        cur["invested"], cur["value"], pct(cur["ret"]), irrs(cur["xirr"]),
        pct(cur["dd"]), cur["avg"]))
    print("  对照：等额%d %s | 满额%d %s | 期初一次性 %s" % (
        (LO + HI) / 2, irrs(flat_all["xirr"]), HI,
        irrs([r for r in results if r["key"] == "flatmax"][0]["all"]["xirr"]),
        irrs(lump_all["xirr"])))
    print("  分年：" + " ".join("%s %s" % (y, irrs(best["years"][y]["xirr"])) for y in years))
    print("[XIRR冠军] %s → %s（均投 %d 元/天）" % (
        champ["label"], irrs(champ["all"]["xirr"]), champ["all"]["avg"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
