#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
515450 · 区间回放（按分数区间给温度曲线染色）

用法：
  python review.py --start 2026-01-01 --title "2026 年度回放" --out review_2026.html
  python review.py --start 2021-02-25 --title "成立以来回放"  --out review_all.html

输出：对应的 .html 与 .csv
"""

import argparse
import csv
import datetime as dt
import json
import os
import sys

import daily_score as ds
import dca_core as bt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BANDS = [
    (0, 20, "#ef4444", "顶部区"),
    (20, 40, "#f97316", "偏热"),
    (40, 60, "#94a3b8", "中性"),
    (60, 80, "#4ade80", "偏冷"),
    (80, 100, "#22c55e", "谷底区"),
]
FWD = 20          # 统计「之后 N 个交易日」的涨跌


def band_of(score):
    for lo, hi, color, name in BANDS:
        if score < hi or hi == 100:
            return lo, hi, color, name
    return BANDS[-1]


def ticks(rows, span):
    """横轴刻度：长区间按年，中区间按月，一个月内按天。"""
    out, seen = [], set()
    step = 1
    if span == "day" and len(rows) > 12:
        step = max(1, len(rows) // 5)
    for i, r in enumerate(rows):
        if span == "year":
            key, label = r["date"][:4], r["date"][:4]
        elif span == "month":
            key, label = r["date"][:7], "%d月" % int(r["date"][5:7])
        else:
            key, label = r["date"], r["date"][5:]
        if key in seen:
            continue
        seen.add(key)
        if span == "day" and i % step:
            continue
        out.append((i, label))
    return out


# --------------------------------------------------------------------------
# 图
# --------------------------------------------------------------------------

def score_chart(rows, span, w=840, h=320):
    pl, pr, pt, pb = 46, 92, 16, 30
    n = len(rows)
    scores = [r["score"] for r in rows]

    def x(i):
        return pl + i * (w - pl - pr) / float(max(n - 1, 1))

    def y(v):
        return h - pb - v / 100.0 * (h - pt - pb)

    out = ['<svg class="chart" viewBox="0 0 %d %d">' % (w, h)]
    for lo, hi, color, name in BANDS:
        out.append('<rect x="%d" y="%.1f" width="%d" height="%.1f" fill="%s" opacity=".07"/>'
                   % (pl, y(hi), w - pl - pr, y(lo) - y(hi), color))
        out.append('<text x="%d" y="%.1f" fill="%s" font-size="10" opacity=".85">%d–%d %s</text>'
                   % (w - pr + 6, (y(hi) + y(lo)) / 2.0 + 3, color, lo, hi, name))
    for v in (0, 20, 40, 60, 80, 100):
        out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#22304a" '
                   'stroke-dasharray="%s"/>' % (pl, y(v), w - pr, y(v),
                                                "0" if v in (0, 100) else "4 4"))
        out.append('<text x="%d" y="%.1f" fill="#6b7d98" font-size="10" text-anchor="end">%d</text>'
                   % (pl - 8, y(v) + 3, v))
    for i in range(1, n):
        color = band_of((scores[i - 1] + scores[i]) / 2.0)[2]
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                   'stroke-width="2.4" stroke-linecap="round"/>'
                   % (x(i - 1), y(scores[i - 1]), x(i), y(scores[i]), color))
    if n <= 45:
        for i, s0 in enumerate(scores):
            out.append('<circle cx="%.1f" cy="%.1f" r="2.6" fill="%s"/>'
                       % (x(i), y(s0), band_of(s0)[2]))
    for i, label in ticks(rows, span):
        out.append('<text x="%.1f" y="%d" fill="#6b7d98" font-size="10" '
                   'text-anchor="middle">%s</text>' % (x(i), h - pb + 18, label))
    out.append("</svg>")
    return "".join(out)


def price_chart(rows, span, w=840, h=200):
    pl, pr, pt, pb = 46, 92, 12, 30
    n = len(rows)
    px = [r["price"] for r in rows]
    lo, hi = min(px), max(px)
    pad = (hi - lo) * 0.12 or 0.01
    lo, hi = lo - pad, hi + pad

    def x(i):
        return pl + i * (w - pl - pr) / float(max(n - 1, 1))

    def y(v):
        return h - pb - (v - lo) / (hi - lo) * (h - pt - pb)

    pts = " ".join("%.1f,%.1f" % (x(i), y(v)) for i, v in enumerate(px))
    area = "%.1f,%.1f " % (x(0), h - pb) + pts + " %.1f,%.1f" % (x(n - 1), h - pb)
    out = ['<svg class="chart" viewBox="0 0 %d %d">' % (w, h)]
    out.append('<defs><linearGradient id="gp" x1="0" y1="0" x2="0" y2="1">'
               '<stop offset="0%%" stop-color="#38bdf8" stop-opacity=".28"/>'
               '<stop offset="100%%" stop-color="#38bdf8" stop-opacity="0"/>'
               '</linearGradient></defs>')
    for k in range(4):
        v = lo + (hi - lo) * k / 3.0
        out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#1c2740"/>'
                   % (pl, y(v), w - pr, y(v)))
        out.append('<text x="%d" y="%.1f" fill="#6b7d98" font-size="10" '
                   'text-anchor="end">%.3f</text>' % (pl - 8, y(v) + 3, v))
    out.append('<polygon points="%s" fill="url(#gp)"/>' % area)
    out.append('<polyline points="%s" fill="none" stroke="#38bdf8" stroke-width="1.8"/>' % pts)
    for i, label in ticks(rows, span):
        out.append('<text x="%.1f" y="%d" fill="#6b7d98" font-size="10" '
                   'text-anchor="middle">%s</text>' % (x(i), h - pb + 18, label))
    out.append("</svg>")
    return "".join(out)


def amount_chart(rows, cfg, w=840, h=120):
    pl, pr, pt, pb = 46, 16, 8, 18
    n = len(rows)
    d = cfg["dca"]
    amts = [ds.dca_amount(r["score"], cfg) for r in rows]
    top = max(amts) * 1.15 or 1
    bw = max(0.7, (w - pl - pr) / float(n) * 0.92)

    out = ['<svg class="chart" viewBox="0 0 %d %d">' % (w, h)]
    for i, a in enumerate(amts):
        color = band_of(rows[i]["score"])[2]
        bh = a / float(top) * (h - pt - pb)
        xx = pl + i * (w - pl - pr) / float(max(n - 1, 1))
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" opacity=".75"/>'
                   % (xx, h - pb - bh, bw, bh, color))
    out.append('<text x="%d" y="%d" fill="#6b7d98" font-size="10">'
               "每天建议金额（元，%d–%d）</text>" % (pl + 4, pt + 9,
                                                    d["min_amount"], d["max_amount"]))
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=["all", "2026", "month"], default=None,
                    help="all=成立以来，2026=今年以来，month=近一个月")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    preset = {
        "all": ("2023-03-16", "全区间回放", "review_all.html"),
        "2026": ("2026-01-01", "2026 年度回放", "review_2026.html"),
        "month": ("__last30__", "近一个月回放", "review_month.html"),
    }.get(args.preset or "")

    start = args.start or (preset[0] if preset else "2026-01-01")
    title = args.title or (preset[1] if preset else "区间回放")
    out = args.out or os.path.join(BASE_DIR, preset[2] if preset else "review.html")

    with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
        cfg = json.load(f)

    frames = ds.load_frames(cfg)
    # 用谷底分代替温度分
    import trough
    tro_rows = trough.build(frames)
    tro_map = {r["date"]: r["score"] for r in tro_rows}
    all_rows = [r for r in bt.build_daily_scores(cfg, frames=frames) if r["date"] in tro_map]
    for r in all_rows:
        r["score"] = tro_map[r["date"]]
    end = args.end or all_rows[-1]["date"]
    if start == "__last30__":
        start = (dt.date.fromisoformat(all_rows[-1]["date"]) - dt.timedelta(days=30)).isoformat()
    rows = [r for r in all_rows if start <= r["date"] <= end]
    if len(rows) < 5:
        print("区间数据不足")
        return 1

    n = len(rows)
    scores = [r["score"] for r in rows]
    first, last = rows[0], rows[-1]
    span_days = (dt.date.fromisoformat(last["date"]) - dt.date.fromisoformat(first["date"])).days
    span = "year" if span_days > 400 else ("month" if span_days > 45 else "day")

    # 之后 20 个交易日的涨跌
    fwd = {}
    for i, r in enumerate(rows):
        j = i + FWD
        if j < n:
            fwd[r["date"]] = (rows[j]["price"] / r["price"] - 1.0) * 100.0

    long_enough = span_days >= 120
    fwd_col = ("之后 %d 日平均涨跌" % FWD) if long_enough else "该区间平均日涨跌"
    band_rows = ""
    for lo, hi, color, name in BANDS:
        sub = [r for r in rows if lo <= r["score"] <= hi]
        if long_enough:
            vals = [fwd[r["date"]] for r in sub if r["date"] in fwd]
            cell = ("%+.2f%%" % (sum(vals) / len(vals))) if vals else "—"
        else:
            daily = [rows[i]["price"] / rows[i - 1]["price"] - 1.0
                     for i in range(1, n) if lo <= rows[i]["score"] <= hi]
            cell = ("%+.3f%%" % (sum(daily) / len(daily) * 100)) if daily else "—"
        band_rows += (
            '<tr><td><span class="dot" style="background:%s"></span>%d–%d %s</td>'
            '<td class="num">%d</td><td class="num">%.0f%%</td>'
            '<td class="num">%s</td></tr>' % (
                color, lo, hi, name, len(sub), len(sub) / float(n) * 100, cell))

    fee = float(cfg["dca"].get("fee_rate", 0.0))
    invested = units = 0.0
    flows = []
    for r in rows:
        a = ds.dca_amount(r["score"], cfg)
        invested += a
        units += a / (1.0 + fee) / r["price"]
        flows.append((dt.date.fromisoformat(r["date"]), -float(a)))
    value = units * last["price"]
    flows.append((dt.date.fromisoformat(last["date"]), value))
    xirr = bt.xirr(flows)
    ret = value / invested - 1.0 if invested else 0.0
    ytd = (last["price"] / first["price"] - 1.0) * 100.0
    years = max((dt.date.fromisoformat(last["date"]) -
                 dt.date.fromisoformat(first["date"])).days / 365.0, 0.1)

    with open(os.path.join(BASE_DIR, "review_template.html"), "r", encoding="utf-8") as f:
        tpl = f.read()

    rep = {
        "__TITLE__": title,
        "__SPAN__": "%s ~ %s" % (first["date"], last["date"]),
        "__DAYS__": str(n),
        "__CHART__": score_chart(rows, span),
        "__PRICE__": price_chart(rows, span),
        "__AMT__": amount_chart(rows, cfg),
        "__BANDS__": band_rows,
        "__MIN__": str(min(scores)), "__MAX__": str(max(scores)),
        "__AVG__": "%.0f" % (sum(scores) / float(n)),
        "__YTD__": "%+.2f%%" % ytd,
        "__FIRSTPX__": "%.3f" % first["price"], "__LASTPX__": "%.3f" % last["price"],
        "__INV__": format(int(invested), ","), "__VAL__": format(int(round(value)), ","),
        "__RET__": "%+.2f%%" % (ret * 100),
        "__PROFIT__": format(int(round(value - invested)), ","),
        "__N_BUY__": str(n), "__LO__": str(cfg["dca"]["min_amount"]),
        "__HI__": str(cfg["dca"]["max_amount"]),
        "__XIRR__": ("%.2f%%" % (xirr * 100)) if (xirr is not None and span_days >= 90) else "—",
        "__YEARLY__": format(int(round(invested / years)), ",") if span_days >= 200 else "",
        "__AVGAMT__": "%d" % round(invested / n),
        "__AVGHINT__": ("年均约 ¥%s" % format(int(round(invested / years)), ",")) if span_days >= 200 else "仅统计本期",
        "__FWD__": str(FWD), "__FWD_COL__": fwd_col,
    }
    for k, v in rep.items():
        tpl = tpl.replace(k, v)

    with open(out, "w", encoding="utf-8") as f:
        f.write(tpl)

    csv_path = os.path.splitext(out)[0] + ".csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as w:
        cw = csv.writer(w)
        cw.writerow(["日期", "温度分", "区间", "复权净值", "建议金额",
                     "之后%d日涨跌" % FWD])
        for r in rows:
            cw.writerow([r["date"], r["score"], band_of(r["score"])[3],
                         "%.4f" % r["price"], ds.dca_amount(r["score"], cfg),
                         ("%.2f" % fwd[r["date"]]) if r["date"] in fwd else ""])

    print("%s：%s ~ %s，%d 个交易日，分数 %d~%d（均值 %.0f）" % (
        title, first["date"], last["date"], n, min(scores), max(scores),
        sum(scores) / n))
    print("净值 %.3f → %.3f（%+.2f%%）；日投投入 %d、市值 %d（%+.2f%%），XIRR %s" % (
        first["price"], last["price"], ytd, invested, value, ret * 100,
        ("%.2f%%" % (xirr * 100)) if xirr is not None else "—"))
    for lo, hi, color, name in BANDS:
        cnt = sum(1 for s in scores if lo <= s <= hi)
        print("  %2d–%3d %-5s %4d 天" % (lo, hi, name, cnt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
