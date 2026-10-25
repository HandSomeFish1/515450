#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共用的数据与打分模块（被 strategy_lab.py 引用）

数据口径：
- 基金净值：天天基金 pingzhongdata（515450 成立以来全部净值），
  用「单位净值 + 分红再投资」还原出复权净值序列，作为回测的价格。
- 沪深300：腾讯日线（分年抓取，覆盖到 2019 年），用于情绪因子。
- 估值与国债：蛋卷 PE 历史、东方财富 10 年国债收益率。

build_daily_scores 逐日重算温度分，每天只用当日及之前的信息（无未来函数）。
"""

import datetime as dt
import json
import os
import re
from bisect import bisect_left, bisect_right

import daily_score as ds

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FUND_CODE = "515450"


# --------------------------------------------------------------------------
# 数据抓取
# --------------------------------------------------------------------------

def fetch_fund_nav(code=FUND_CODE):
    """返回 (单位净值序列, 复权净值序列)，均为 [(date, value), ...] 升序。"""
    url = "https://fund.eastmoney.com/pingzhongdata/%s.js" % code
    s = ds.http_get(url, referer="https://fund.eastmoney.com/%s.html" % code, timeout=30)
    nav_raw = json.loads(re.search(r"Data_netWorthTrend\s*=\s*(\[.*?\]);", s).group(1))
    ac_raw = json.loads(re.search(r"Data_ACWorthTrend\s*=\s*(\[.*?\]);", s).group(1))

    nav = []
    for r in nav_raw:
        d = dt.datetime.fromtimestamp(r["x"] / 1000).date().isoformat()
        nav.append((d, float(r["y"])))
    ac = {}
    for r in ac_raw:
        d = dt.datetime.fromtimestamp(r[0] / 1000).date().isoformat()
        ac[d] = float(r[1])

    # 分红 = (累计净值变化) − (单位净值变化)
    div = {}
    for i in range(1, len(nav)):
        d0, v0 = nav[i - 1]
        d1, v1 = nav[i]
        if d0 in ac and d1 in ac:
            d = (ac[d1] - ac[d0]) - (v1 - v0)
            if d > 1e-6:
                div[d1] = d

    # 复权净值：分红当日按除权价再投资，最后缩放回最新单位净值，方便和现在的净值对照
    adj = [(nav[0][0], 1.0)]
    for i in range(1, len(nav)):
        d0, v0 = nav[i - 1]
        d1, v1 = nav[i]
        r = (v1 + div.get(d1, 0.0)) / v0
        adj.append((d1, adj[-1][1] * r))
    k = nav[-1][1] / adj[-1][1]
    adj = [(d, v * k) for d, v in adj]
    return nav, adj


def fetch_kline_range(tencent_code, start="2019-01-01", end=None):
    """腾讯日线，按 2 年窗口分页抓取，返回 [(date, close), ...] 升序。"""
    end_d = dt.date.fromisoformat(end) if end else dt.date.today()
    cur = dt.date.fromisoformat(start)
    out = {}
    while cur <= end_d:
        nxt = min(cur + dt.timedelta(days=730), end_d)
        url = ("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
               "?param=%s,day,%s,%s,1000,qfq" % (tencent_code, cur, nxt))
        data = ds.http_json(url, referer="https://gu.qq.com/")["data"][tencent_code]
        rows = (data.get("qfqday") or data.get("day") or []) if isinstance(data, dict) else []
        for r in rows:
            try:
                out[r[0]] = float(r[2])
            except (IndexError, TypeError, ValueError):
                pass
        cur = nxt + dt.timedelta(days=1)
    return sorted(out.items())


# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------

def asof(pairs, dates, d):
    i = bisect_right(dates, d) - 1
    return pairs[i][1] if i >= 0 else None


def xnpv(rate, flows):
    t0 = flows[0][0]
    return sum(cf / (1.0 + rate) ** ((d - t0).days / 365.0) for d, cf in flows)


def xirr(flows):
    """资金加权年化收益率（二分法）。"""
    if len(flows) < 2:
        return None
    lo, hi = -0.9999, 10.0
    f_lo, f_hi = xnpv(lo, flows), xnpv(hi, flows)
    if f_lo * f_hi > 0:
        return None
    for _ in range(300):
        mid = (lo + hi) / 2.0
        v = xnpv(mid, flows)
        if abs(v) < 1e-7:
            return mid
        if v * f_lo > 0:
            lo, f_lo = mid, v
        else:
            hi = mid
    return (lo + hi) / 2.0


def round_to(x, step):
    return int(round(x / float(step)) * step)


# --------------------------------------------------------------------------
# 逐日温度分
# --------------------------------------------------------------------------

def build_ledger(cfg, frames=None, start=None, score_map=None, mirror=False, gap_map=None):
    """按定投规则回放一份账本。

    支持「实际记录 + 规则记录」混排：
      ledger_start ~ rule_from 之间用 actual_amount（用户真实投入的固定金额），
      rule_from 之后按分数规则计算。

    score_map: {date: score} 覆盖当日分数（用于谷底分替代温度分）
    mirror:    True 时分数越高投越多（谷底分语义）
    """
    rows = build_daily_scores(cfg, frames=frames)
    d = cfg.get("dca") or {}
    lo = float(d.get("min_amount", 100))
    hi = float(d.get("max_amount", 500))
    step = float(d.get("round_to", 10))
    a_hi = float(d.get("anchor_high_score", 0))
    a_lo = float(d.get("anchor_low_score", 50))
    start = start or d.get("ledger_start") or "2021-02-25"
    actual = d.get("actual_amount")
    rule_from = d.get("rule_from")
    fee = float(d.get("fee_rate", 0.0))

    def amount(score, gap=None):
        if d.get("score_mode") in ("tiered", "trough"):
            return ds.dca_amount(score, cfg, gap)
        if mirror:
            hi_a = float(d.get("trough_anchor_high", 80))
            lo_a = float(d.get("trough_anchor_low", 50))
            t = (score - lo_a) / (hi_a - lo_a) if hi_a != lo_a else 0.5
        else:
            t = (a_lo - score) / (a_lo - a_hi) if a_lo != a_hi else 0.5
        return int(max(lo, min(hi, round_to(lo + min(max(t, 0.0), 1.0) * (hi - lo), step))))

    out, inv, units, fees = [], 0.0, 0.0, 0.0
    for r in rows:
        if r["date"] < start:
            continue
        sc = score_map.get(r["date"], r["score"]) if score_map else r["score"]
        gp = gap_map.get(r["date"]) if gap_map else None
        manual = actual is not None and (rule_from is None or r["date"] < rule_from)
        a = float(actual) if manual else amount(sc, gp)
        net = a / (1.0 + fee)                    # 外扣法：先扣申购费再买份额
        inv += a
        fees += a - net
        units += net / r["price"]
        out.append({"date": r["date"], "score": sc, "amount": int(a),
                    "manual": manual, "nav": r["price"], "units": units,
                    "invested": inv, "fee": a - net,
                    "value": units * r["price"]})

    if not out:
        return {"rows": [], "invested": 0.0, "value": 0.0, "units": 0.0,
                "cost": 0.0, "xirr": None, "start": start, "n": 0, "pnl": 0.0,
                "pnl_pct": 0.0, "manual_until": None, "fee_total": 0.0}

    flows = [(dt.date.fromisoformat(x["date"]), -float(x["amount"])) for x in out]
    flows.append((dt.date.fromisoformat(out[-1]["date"]), out[-1]["value"]))
    manual_days = [x["date"] for x in out if x["manual"]]
    return {
        "rows": out, "invested": inv, "value": out[-1]["value"], "units": units,
        "cost": inv / units if units else 0.0, "xirr": xirr(flows),
        "start": out[0]["date"], "n": len(out), "fee_total": fees,
        "pnl": out[-1]["value"] - inv,
        "pnl_pct": (out[-1]["value"] / inv - 1.0) if inv else 0.0,
        "manual_until": manual_days[-1] if manual_days else None,
    }


def build_daily_scores(cfg, frames=None, warmup=250):
    """返回 [{date, price, score, ...}, ...]，price 为复权净值。

    frames 为 daily_score.load_frames() 的结果；不传则自己抓一遍。
    """
    if not frames:
        frames = ds.load_frames(cfg)
    adj = frames["nav_adj"]
    bench = frames["bench"]
    val = frames["val"]
    pe_hist = frames["pe"]
    bond = frames["bond"]

    payout = val["div"] / 100.0 * val["pe"]       # 派息率（由当前股息率与 PE 反推）
    pe_pairs = [(p[0], p[1]) for p in pe_hist if p[1] > 0]
    pe_dates = [p[0] for p in pe_pairs]
    pe_vals = [p[1] for p in pe_pairs]
    bond_dates = [b[0] for b in bond]

    div_hist = [(d, 100.0 * payout / pe) for d, pe in pe_pairs]
    spread_hist = []
    for d, dv in div_hist:
        y = asof(bond, bond_dates, d)
        if y is not None:
            spread_hist.append((d, dv - y))
    sp_dates = [s[0] for s in spread_hist]
    sp_vals = [s[1] for s in spread_hist]

    prices = [p for _, p in adj]
    b_dates = [d for d, _ in bench]
    b_closes = [c for _, c in bench]
    b_map = dict(zip(b_dates, b_closes))

    R, W = cfg["ranges"], cfg["weights"]
    years = cfg.get("percentile_years", 10)
    scale = cfg["sentiment_scale"]

    rows = []
    for i, (d, px) in enumerate(adj):
        if i < warmup or i < 61:
            continue
        ma = sum(prices[i - warmup + 1:i + 1]) / float(warmup)
        bias = (px / ma - 1.0) * 100.0
        r14 = ds.rsi(prices[:i + 1], 14)
        mom60 = (px / prices[i - 60] - 1.0) * 100.0

        bi = bisect_right(b_dates, d) - 1
        if bi < 60:
            continue
        b_close = b_map.get(d, b_closes[bi])
        mom300 = (b_close / b_closes[bi - 60] - 1.0) * 100.0
        env = min(max(50.0 + scale * (mom60 - mom300), 0.0), 100.0)

        pe_now = asof(list(zip(pe_dates, pe_vals)), pe_dates, d)
        if not pe_now:
            continue
        div_now = 100.0 * payout / pe_now
        y10 = asof(bond, bond_dates, d)
        if y10 is None:
            continue
        spread_now = div_now - y10

        lo = bisect_left(sp_dates, (dt.date.fromisoformat(d)
                                    - dt.timedelta(days=365 * years)).isoformat())
        window = sp_vals[lo:bisect_right(sp_dates, d)]
        if len(window) < 100:
            continue
        spread_pct = 100.0 - sum(1 for x in window if x <= spread_now) / float(len(window)) * 100.0

        total = int(round(
            ds.linmap(spread_pct, *R["spread_pct"]) * W["spread"] +
            ds.linmap(div_now, *R["div_yield"]) * W["div"] +
            ds.linmap(r14, *R["rsi"]) * W["rsi"] +
            ds.linmap(bias, *R["bias"]) * W["bias"] +
            ds.linmap(env, *R["env"]) * W["env"]))
        rows.append({
            "date": d, "price": px, "score": total, "spread_pct": spread_pct,
            "div": div_now, "y10": y10, "rsi": r14, "bias": bias, "env": env,
        })
    return rows
