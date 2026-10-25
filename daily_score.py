#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
515450 红利低波 · 综合温度计 —— 每日自动打分

流程：
  1. 拉取 515450 日线（腾讯）→ RSI14、年线 BIAS、60 日动量
  2. 拉取 沪深300 日线（腾讯）→ 60 日动量 → 相对强弱情绪
  3. 拉取 中证红利低波(CSIH30269) 股息率 / PE / PE 历史（蛋卷）
  4. 拉取 中国 10 年期国债收益率历史（东方财富数据中心）
  5. 计算利差分位（股息率−10Y 在过去 10 年中的排名，越低越便宜）
  6. 按原始网页权重加权 → 生成 report.html、history.csv、latest.json
  7. 可选：把 report.html 复制到桌面

仅用标准库，Python 3.8+。
"""

import argparse
import csv
import datetime as dt
import json
import os
import ssl
import sys
import time
import traceback
import urllib.request
from trough import band_action as trough_band

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
_DEADLINE = [None]        # 整体取数截止时间（time.time()）


def set_deadline(seconds):
    _DEADLINE[0] = time.time() + seconds


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def http_get(url, referer=None, timeout=15, retries=3, encoding="utf-8"):
    last = None
    for i in range(retries):
        if _DEADLINE[0] and time.time() > _DEADLINE[0]:
            raise RuntimeError("取数超时（超过整体时限）：%s" % url)
        try:
            headers = {"User-Agent": UA, "Accept": "*/*"}
            if referer:
                headers["Referer"] = referer
            req = urllib.request.Request(url, headers=headers)
            ctx = ssl._create_unverified_context()
            tmo = timeout
            if _DEADLINE[0]:
                tmo = max(3.0, min(timeout, _DEADLINE[0] - time.time()))
            with urllib.request.urlopen(req, timeout=tmo, context=ctx) as r:
                raw = r.read()
            return raw.decode(encoding, "ignore")
        except Exception as e:          # noqa: BLE001 - 上游不稳定，统一重试
            last = e
            if _DEADLINE[0] and time.time() > _DEADLINE[0]:
                raise RuntimeError("取数超时（超过整体时限）：%s" % url)
            time.sleep(min(1.2 * (i + 1), 3.0))
    raise RuntimeError("请求失败 %s: %s" % (url, last))


def http_json(url, referer=None, timeout=15, retries=3):
    return json.loads(http_get(url, referer=referer, timeout=timeout, retries=retries))


# --------------------------------------------------------------------------
# 数据源
# --------------------------------------------------------------------------

def fetch_kline(tencent_code, count=900):
    """腾讯日线，返回 [(date, close), ...]，按日期升序。"""
    url = ("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           "?param=%s,day,,,%d,qfq" % (tencent_code, count))
    data = http_json(url, referer="https://gu.qq.com/")["data"][tencent_code]
    rows = data.get("qfqday") or data.get("day") or []
    out = []
    for r in rows:
        try:
            out.append((r[0], float(r[2])))
        except (IndexError, TypeError, ValueError):
            continue
    out.sort(key=lambda x: x[0])
    if len(out) < 30:
        raise RuntimeError("K线数据过少: %s rows=%d" % (tencent_code, len(out)))
    return out


def fetch_kline_range(tencent_code, start="2019-01-01", end=None):
    """腾讯日线，按 2 年窗口分页抓取，返回 [(date, close), ...] 升序。"""
    end_d = dt.date.fromisoformat(end) if end else dt.date.today()
    cur = dt.date.fromisoformat(start)
    out = {}
    while cur <= end_d:
        nxt = min(cur + dt.timedelta(days=730), end_d)
        url = ("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
               "?param=%s,day,%s,%s,1000,qfq" % (tencent_code, cur, nxt))
        data = http_json(url, referer="https://gu.qq.com/")["data"][tencent_code]
        rows = (data.get("qfqday") or data.get("day") or []) if isinstance(data, dict) else []
        for r in rows:
            try:
                out[r[0]] = float(r[2])
            except (IndexError, TypeError, ValueError):
                pass
        cur = nxt + dt.timedelta(days=1)
    return sorted(out.items())


def market_closed_today():
    """A 股当天是否已经收盘（15:05 之后）。"""
    now = dt.datetime.now()
    return now.hour * 60 + now.minute >= 15 * 60 + 5


def in_trading_session(now=None):
    """是否处于 A 股连续竞价时段（9:30–11:30、13:00–15:00，仅限工作日）。"""
    now = now or dt.datetime.now()
    if now.weekday() >= 5:
        return False
    m = now.hour * 60 + now.minute
    return (9 * 60 + 30 <= m < 11 * 60 + 30) or (13 * 60 <= m < 15 * 60)


def drop_partial(pairs, force_intraday=False):
    """不在交易时段时，丢掉当天还没走完的 K 线，只用最近一个已收盘交易日；盘中则保留实时价。"""
    if force_intraday:
        return pairs
    now = dt.datetime.now()
    today = now.date().isoformat()
    if pairs and pairs[-1][0] == today and now.hour * 60 + now.minute < 15 * 60 \
            and not in_trading_session(now):
        return pairs[:-1]
    return pairs


def fetch_realtime_price(tencent_code):
    """腾讯实时行情的最新价（盘中用）。"""
    txt = _http("https://qt.gtimg.cn/q=%s" % tencent_code,
                referer="https://gu.qq.com/", encoding="gbk")
    parts = txt.split('"')[1].split("~")
    price = float(parts[3])
    if price <= 0:
        raise RuntimeError("实时价异常")
    return price


def patch_nav_latest(nav_adj, etf, cfg):
    """基金净值通常 T+1 才公布。若 ETF 已有更新的交易日，
    就用「ETF 价格 × 净值/价格比率」补上一点，保证当天分数能算出来。

    - 盘中：用腾讯实时价（你点开的那个时刻）
    - 收盘后：用 ETF 当日收盘价
    """
    if not nav_adj or not etf:
        return nav_adj
    etf_map = dict(etf)
    adj_last = nav_adj[-1][0]
    etf_last = etf[-1][0]
    if etf_last <= adj_last:
        return nav_adj

    ref = None
    for d in reversed([x[0] for x in etf]):
        if d <= adj_last and d in dict(nav_adj):
            ref = d
            break
    if not ref:
        return nav_adj

    ratio = dict(nav_adj)[ref] / etf_map[ref]
    val = None
    if in_trading_session():
        try:
            rt = fetch_realtime_price(cfg["tencent_code"])
            val = rt * ratio
            print("     盘中：用实时价 %.3f 补 %s" % (rt, etf_last))
        except Exception:                     # noqa: BLE001
            val = None
    if val is None:
        val = etf[-1][1] * ratio
        print("     净值缺 %s，用 ETF 收盘 %.3f 补上（折算 %.4f）" % (etf_last, etf[-1][1], val))
    return nav_adj + [(etf_last, val)]


def load_frames(cfg):
    """一次性抓齐所有数据，供打分和账本共用（避免重复请求、减少等待）。"""
    import dca_core                       # 延迟导入，避免循环依赖

    intraday = bool(cfg.get("use_intraday", False))
    print("  · 取 515450 日线…", flush=True)
    etf = drop_partial(fetch_kline(cfg["tencent_code"], 900), intraday)
    print("  · 取 沪深300 日线…", flush=True)
    bench = drop_partial(fetch_kline_range(cfg["benchmark_tencent_code"], "2019-01-01"), intraday)
    print("  · 取 指数估值…", flush=True)
    val = fetch_index_valuation(cfg["index_code"])
    pe = fetch_valuation_history(cfg["index_code"])
    print("  · 取 10 年国债收益率…", flush=True)
    bond = fetch_cn10y()
    print("  · 取 基金复权净值…", flush=True)
    _, nav_adj = dca_core.fetch_fund_nav(cfg.get("fund_code", "515450"))
    nav_adj = patch_nav_latest(nav_adj, etf, cfg)
    return {"etf": etf, "bench": bench, "val": val, "pe": pe,
            "bond": bond, "nav_adj": nav_adj}


def fetch_index_valuation(index_code):
    """蛋卷指数估值：股息率、PE、PE 分位。"""
    url = "https://danjuanfunds.com/djapi/index_eva/detail/%s" % index_code
    d = http_json(url, referer="https://danjuanfunds.com/")["data"]
    return {
        "name": d.get("name"),
        "pe": float(d["pe"]),
        "pb": float(d["pb"]),
        "pe_pct": float(d["pe_percentile"]) * 100.0,
        "div": float(d["yeild"]) * 100.0,
        "ts": dt.datetime.fromtimestamp(d["ts"] / 1000.0).date().isoformat(),
    }


def fetch_valuation_history(index_code):
    """蛋卷 PE 历史，返回 [(date, pe), ...] 升序。"""
    url = "https://danjuanfunds.com/djapi/index_eva/pe_history/%s?day=all" % index_code
    data = http_json(url, referer="https://danjuanfunds.com/")["data"]
    rows = data.get("index_eva_pe_growths") or data.get("pe_growths") or []
    out = []
    for r in rows:
        try:
            ts = dt.datetime.fromtimestamp(r["ts"] / 1000.0).date().isoformat()
            out.append((ts, float(r["pe"])))
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda x: x[0])
    if len(out) < 60:
        raise RuntimeError("估值历史过少: %d" % len(out))
    return out


def fetch_cn10y(years=11):
    """东方财富 中国 10 年期国债收益率，返回 [(date, yield%), ...] 升序。"""
    cutoff = (dt.date.today() - dt.timedelta(days=365 * years + 30)).isoformat()
    base = ("https://datacenter.eastmoney.com/api/data/get"
            "?type=RPTA_WEB_TREASURYYIELD&sty=ALL&st=SOLAR_DATE&sr=-1"
            "&token=894050c76af8597a853f5b408b759f5d&ps=500&p=")
    out, page = [], 1
    while page <= 8:
        v = http_json(base + str(page),
                      referer="https://data.eastmoney.com/cjsj/zmgzsyl.html")
        rows = ((v.get("result") or {}).get("data")) or []
        if not rows:
            break
        stop = False
        for r in rows:
            date = str(r.get("SOLAR_DATE") or "")[:10]
            y = r.get("EMM00166466")
            if not date or y in (None, "-", ""):
                continue
            if date < cutoff:
                stop = True
                continue
            out.append((date, float(y)))
        if stop:
            break
        page += 1
        time.sleep(0.4)
    out.sort(key=lambda x: x[0])
    if not out:
        raise RuntimeError("未取到国债收益率")
    return out


# --------------------------------------------------------------------------
# 指标
# --------------------------------------------------------------------------

def rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def pct_change(closes, n):
    if len(closes) <= n or closes[-1 - n] == 0:
        return None
    return (closes[-1] / closes[-1 - n] - 1.0) * 100.0


def percentile_rank(series, value):
    if not series:
        return None
    return sum(1 for x in series if x <= value) / float(len(series)) * 100.0


def linmap(v, a, b):
    if b == a:
        return 0.0
    return min(max((v - a) / float(b - a), 0.0), 1.0)


# --------------------------------------------------------------------------
# 打分
# --------------------------------------------------------------------------

def band(total):
    if total <= 20:
        return ("#22c55e", "rgba(34,197,94,.16)", "极佳买点：重仓 6 成以上",
                "利差与估值同时处于历史低位，安全垫最厚。")
    if total <= 40:
        return ("#4ade80", "rgba(74,222,128,.16)", "偏冷：分批建仓 2-3 成",
                "估值偏便宜，可小步分批，留足后续加仓空间。")
    if total <= 60:
        return ("#94a3b8", "rgba(148,163,184,.16)", "中性：持有观望，不买不卖",
                "性价比一般，等待更明确的信号再加仓或减仓。")
    if total <= 80:
        return ("#f59e0b", "rgba(245,158,11,.16)", "偏热：警惕回调，分批止盈",
                "估值与情绪偏贵，逐步兑现浮盈，不追高。")
    return ("#ef4444", "rgba(239,68,68,.16)", "极度高估：适合清仓卖出",
            "历史高位区间，回撤风险显著大于上涨空间。")


def dca_amount(score, cfg, gap=None):
    """按分数（以及跌破 20 日线的幅度）算本期定投金额。

    score_mode=tiered：分档 50 / 100 / 650，最高档在跌破均线超过阈值时
                       每多 1 个百分点加 addon_per_pp 元；
    score_mode=trough：50 分投下限、80 分投上限；
    其它（温度分）：高位锚点投上限、低位锚点投下限。
    """
    d = cfg.get("dca") or {}
    lo = float(d.get("min_amount", 100))
    hi = float(d.get("max_amount", 1000))
    step = float(d.get("round_to", 10))
    mode = d.get("score_mode")

    if mode == "tiered":
        tiers = d.get("tiers") or [{"below": 20, "amount": 50},
                                   {"below": 75, "amount": 100},
                                   {"below": 999, "amount": 650}]
        amt = float(tiers[-1]["amount"])
        for t in tiers:
            if score < float(t["below"]):
                amt = float(t["amount"])
                break
        per = float(d.get("addon_per_pp", 0))
        thr = float(d.get("addon_threshold", 3.0))
        hi_from = float(d.get("addon_from_score", 75))
        if per and gap is not None and score >= hi_from and gap > thr:
            amt += (gap - thr) * per
        return int(round(amt))

    if mode == "trough":
        a_hi = float(d.get("trough_anchor_high", 80))
        a_lo = float(d.get("trough_anchor_low", 50))
        t = (score - a_lo) / (a_hi - a_lo) if a_hi != a_lo else 0.5
    else:
        a_hi = float(d.get("anchor_high_score", 20))
        a_lo = float(d.get("anchor_low_score", 60))
        t = (a_lo - score) / (a_lo - a_hi) if a_lo != a_hi else 0.5
    amt = lo + min(max(t, 0.0), 1.0) * (hi - lo)
    return int(round(amt / step) * step)


def compute(cfg, frames=None):
    f = frames or load_frames(cfg)
    k = f["etf"]
    k300 = f["bench"]
    val = f["val"]
    hist = f["pe"]
    bond = f["bond"]
    live = (k[-1][0] == dt.date.today().isoformat()) and in_trading_session()

    closes = [c for _, c in k]
    k300_closes = [c for _, c in k300]

    price = closes[-1]
    ma250 = (sum(closes[-250:]) / 250.0 if len(closes) >= 250
             else sum(closes) / len(closes))
    bias = (price / ma250 - 1.0) * 100.0
    rsi14 = rsi(closes, 14)
    mom60 = pct_change(closes, 60)
    mom60_300 = pct_change(k300_closes, 60)

    # 情绪：红利相对沪深300 的 60 日超额收益。跑输 = 被抽血 = 便宜（低分）。
    if mom60 is not None and mom60_300 is not None:
        rs60 = mom60 - mom60_300
        env = 50.0 + cfg["sentiment_scale"] * rs60      # 每 1pp 超额 ≈ 2.5 分
        env = min(max(env, 0.0), 100.0)
    else:
        rs60, env = None, 50.0

    # 股息率历史序列：股息率 ∝ 1/PE（假设派息率稳定）
    div_hist = [(d, val["div"] * val["pe"] / pe) for d, pe in hist if pe > 0]
    bond_map = list(bond)
    years = cfg.get("percentile_years", 10)
    cutoff = (dt.date.today() - dt.timedelta(days=365 * years)).isoformat()

    spreads, j = [], 0
    for d, dv in div_hist:
        while j + 1 < len(bond_map) and bond_map[j + 1][0] <= d:
            j += 1
        if bond_map[j][0] <= d and d >= cutoff:
            spreads.append(dv - bond_map[j][1])

    y10_now = bond[-1][1]
    spread_now = val["div"] - y10_now
    if spreads:
        pct_spread = percentile_rank(spreads, spread_now)
        spread_pct = 100.0 - pct_spread      # 0 = 利差最大 = 最便宜
    else:
        spread_pct = 50.0
    div_pct = percentile_rank([dv for d, dv in div_hist if d >= cutoff],
                              val["div"]) or 50.0

    R, W = cfg["ranges"], cfg["weights"]
    s_spread = linmap(spread_pct, *R["spread_pct"])
    s_div = linmap(val["div"], *R["div_yield"])
    s_rsi = linmap(rsi14 if rsi14 is not None else 50, *R["rsi"])
    s_bias = linmap(bias, *R["bias"])
    s_env = linmap(env, *R["env"])
    total = int(round(s_spread * W["spread"] + s_div * W["div"] +
                      s_rsi * W["rsi"] + s_bias * W["bias"] + s_env * W["env"]))

    factors = [
        {"key": "spread", "name": "利差分位", "sub": "股息率 − 10年国债",
         "value": "%.0f%%" % spread_pct, "score": s_spread, "weight": W["spread"],
         "desc": "0% = 利差历史最大（最便宜）"},
        {"key": "div", "name": "指数股息率", "sub": "中证红利低波",
         "value": "%.2f%%" % val["div"], "score": s_div, "weight": W["div"],
         "desc": "5.5% 以上记 0 分，3.5% 以下记 100 分"},
        {"key": "rsi", "name": "RSI14", "sub": "515450 日线",
         "value": "%.1f" % (rsi14 if rsi14 is not None else 50), "score": s_rsi,
         "weight": W["rsi"], "desc": "20 以下超卖，80 以上超买"},
        {"key": "bias", "name": "年线 BIAS", "sub": "相对 MA250",
         "value": "%+.1f%%" % bias, "score": s_bias, "weight": W["bias"],
         "desc": "−15% 以下记 0 分，+15% 以上记 100 分"},
        {"key": "env", "name": "市场情绪", "sub": "红利相对沪深300 60日强弱",
         "value": "%.0f" % env, "score": s_env, "weight": W["env"],
         "desc": "0=红利被极致抽血（买），100=全面牛市（卖）"},
    ]

    return {
        "date": k[-1][0], "price": price, "ma250": ma250, "bias": bias,
        "rsi14": rsi14, "mom60": mom60, "mom60_300": mom60_300, "rs60": rs60,
        "env": env, "div": val["div"], "pe": val["pe"], "pb": val["pb"],
        "pe_pct": val["pe_pct"], "y10": y10_now, "y10_date": bond[-1][0],
        "spread": spread_now, "spread_pct": spread_pct, "div_pct": div_pct,
        "spreads_n": len(spreads), "factors": factors, "total": total,
        "dca_amount": dca_amount(total, cfg),
        "intraday": live, "quote_time": dt.datetime.now().strftime("%H:%M:%S"),
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "index_name": val["name"] or cfg["index_name"],
    }


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------

def load_history(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save_history(path, res):
    fields = ["date", "price", "div", "y10", "spread", "spread_pct", "div_pct",
              "rsi14", "bias", "env", "total", "action", "generated"]
    rows = load_history(path)
    new = {
        "date": res["date"], "price": "%.3f" % res["price"],
        "div": "%.2f" % res["div"], "y10": "%.4f" % res["y10"],
        "spread": "%.4f" % res["spread"], "spread_pct": "%.1f" % res["spread_pct"],
        "div_pct": "%.1f" % res["div_pct"],
        "rsi14": "%.1f" % (res["rsi14"] or 50), "bias": "%.2f" % res["bias"],
        "env": "%.1f" % res["env"], "total": str(res["total"]),
        "action": band(res["total"])[2], "generated": res["generated"],
    }
    rows = [r for r in rows if r.get("date") != res["date"]]
    rows.append(new)
    rows.sort(key=lambda r: r.get("date", ""))
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    return rows[-60:]


def fmt(v, digits=2):
    return ("%." + str(digits) + "f") % v


def spark_svg(rows, height=110):
    vals = [int(r["total"]) for r in rows if str(r.get("total", "")).isdigit()]
    if not vals:
        return '<div class="empty">还没有历史记录，从下一个交易日起每天累积一条。</div>'
    if len(vals) == 1:
        return ('<div class="spark-one">首日记录：温度 <b>%d</b>，明日起显示走势曲线。</div>'
                % vals[0])
    w, h, pad = 640, height, 12
    n = len(vals)
    pts = ["%.1f,%.1f" % (pad + i * (w - 2 * pad) / float(n - 1),
                          h - pad - (v / 100.0) * (h - 2 * pad))
           for i, v in enumerate(vals)]
    area = "%.1f,%.1f " % (pad, h - pad) + " ".join(pts) + \
           " %.1f,%.1f" % (w - pad, h - pad)
    last = vals[-1]
    return (
        '<svg class="spark" viewBox="0 0 %d %d" preserveAspectRatio="none">'
        '<defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%%" stop-color="#38bdf8" stop-opacity=".35"/>'
        '<stop offset="100%%" stop-color="#38bdf8" stop-opacity="0"/>'
        '</linearGradient></defs>'
        '<polygon points="%s" fill="url(#g1)"/>'
        '<polyline points="%s" fill="none" stroke="#38bdf8" stroke-width="2" '
        'stroke-linejoin="round" stroke-linecap="round"/>'
        '<circle cx="%.1f" cy="%.1f" r="3.5" fill="#38bdf8"/>'
        '</svg>'
        '<div class="spark-meta"><span>区间 %d 条</span><span>最新 %d</span>'
        '<span>最高 %d · 最低 %d</span></div>'
        % (w, h, area, " ".join(pts),
           pad + (n - 1) * (w - 2 * pad) / float(n - 1),
           h - pad - (last / 100.0) * (h - 2 * pad),
           n, last, max(vals), min(vals))
    )


def build_rows_html(res):
    out = []
    for f in res["factors"]:
        s = f["score"] * 100.0
        color = "#22c55e" if s < 40 else ("#f59e0b" if s > 60 else "#38bdf8")
        out.append(
            '<tr>'
            '<td><div class="f-name">%s</div><div class="f-sub">%s</div></td>'
            '<td class="num strong">%s</td>'
            '<td class="bar-cell"><div class="mini"><i style="width:%.0f%%;background:%s">'
            '</i></div><span class="mini-num">%.0f</span></td>'
            '<td class="num muted">%d%%</td>'
            '<td class="desc muted">%s</td>'
            '</tr>' % (f["name"], f["sub"], f["value"], s, color, s,
                       f["weight"], f["desc"]))
    return "\n".join(out)


def ledger_block(res, cfg, ledger):
    """今日定投 + 账本 的 HTML 片段。"""
    d = cfg.get("dca") or {}
    lo = float(d.get("min_amount", 100))
    hi = float(d.get("max_amount", 500))
    score = res["total"]
    if d.get("score_mode") == "tiered":
        tiers = d.get("tiers") or []
        base = float(tiers[-1]["amount"]) if tiers else lo
        for t in tiers:
            if score < float(t["below"]):
                base = float(t["amount"])
                break
        thr = float(d.get("addon_threshold", 3.0))
        per = float(d.get("addon_per_pp", 0))
        gap = res.get("gap")
        if per and gap is not None and score >= float(d.get("addon_from_score", 75)) and gap > thr:
            formula = "650 + (%.1f − %.0f) × %.0f = %d 元" % (
                gap, thr, per, res["dca_amount"])
        elif score < 20:
            formula = "谷底分 %d &lt; 20 → 投 %d 元" % (score, res["dca_amount"])
        elif score < 75:
            formula = "谷底分 %d 在 20–75 → 投 %d 元" % (score, res["dca_amount"])
        else:
            formula = "谷底分 %d ≥ 75，未跌破均线 %.0f%% → 投 %d 元" % (score, thr, res["dca_amount"])
    elif d.get("score_mode") == "trough":
        a_hi = float(d.get("trough_anchor_high", 80))
        a_lo = float(d.get("trough_anchor_low", 50))
        if score <= a_lo:
            formula = "%d 分 ≤ %d 分，按下限投 %d 元" % (score, a_lo, lo)
        elif score >= a_hi:
            formula = "%d 分 ≥ %d 分，按上限投 %d 元" % (score, a_hi, hi)
        else:
            formula = "%d 分 → %d + (%d − %d) × %.0f = %d 元" % (
                score, lo, score, a_lo, (hi - lo) / (a_hi - a_lo), res["dca_amount"])
    else:
        a_hi = float(d.get("anchor_high_score", 0))
        a_lo = float(d.get("anchor_low_score", 50))
        if score >= a_lo:
            formula = "%d 分 ≥ %d 分，按下限投 %d 元" % (score, a_lo, lo)
        elif score <= a_hi:
            formula = "%d 分 ≤ %d 分，按上限投 %d 元" % (score, a_hi, hi)
        else:
            formula = "%d 分 → %d + (%d − %d) × %.0f = %d 元" % (
                score, lo, a_lo, score, (hi - lo) / (a_lo - a_hi), res["dca_amount"])

    if not ledger or not ledger["rows"]:
        return ('<div class="dca-empty">账本还没开始：下一个交易日会按规则自动记第一笔'
                '（起始日 %s）。</div>' % (ledger or {}).get("start", "—"))

    rows_html = "".join(
        '<tr><td>%s</td><td class="num">%d</td><td class="num strong">%d</td>'
        '<td class="num">%.3f</td><td class="num">%s</td>'
        '<td class="num" style="color:%s">%s</td>'
        '<td class="num muted">%s</td></tr>' % (
            x["date"], x["score"], x["amount"], x["nav"],
            format(int(x["invested"]), ","),
            "#22c55e" if x["value"] >= x["invested"] else "#ef4444",
            format(int(round(x["value"])), ","),
            "实际" if x.get("manual") else "规则")
        for x in ledger["rows"])

    pnl_color = "#22c55e" if ledger["pnl"] >= 0 else "#ef4444"
    span_days = (dt.date.fromisoformat(ledger["rows"][-1]["date"]) -
                 dt.date.fromisoformat(ledger["start"])).days
    xirr_txt = ("%.2f%%" % (ledger["xirr"] * 100)) if (
        ledger["xirr"] is not None and span_days >= 60) else "—"
    if ledger.get("manual_until"):
        note = ("账本自 %s 起：%s 及之前按你实际的每天 %d 元记，之后按谷底分规则自动记录。"
                % (ledger["start"], ledger["manual_until"], cfg["dca"].get("actual_amount", 100)))
    else:
        note = "账本自 %s 起按规则回放，缺跑的日子自动补算。" % ledger["start"]
    if span_days < 60:
        note += "（账户还不满 60 天，XIRR 暂不展示）"
    if float(cfg["dca"].get("fee_rate", 0.0)) > 0:
        note += "；每笔按 %.2f%% 扣申购费（外扣法），已计入成本。" % (
            float(cfg["dca"]["fee_rate"]) * 100)
    if res.get("intraday"):
        note += "盘中只更新温度和建议金额，账本要等当晚净值公布后才记这一笔。"

    return (
        '<div class="dca-top">'
        '<div><div class="dca-amt">¥%s</div>'
        '<div class="dca-formula">%s</div></div>'
        '<div class="dca-metrics">'
        '<div><span class="k">累计投入</span><b>¥%s</b></div>'
        '<div><span class="k">持仓市值</span><b>¥%s</b></div>'
        '<div><span class="k">浮动盈亏</span><b style="color:%s">%s（%s）</b></div>'
        '<div><span class="k">累计手续费</span><b>¥%.2f</b></div>'
        '<div><span class="k">平均成本</span><b>%.3f</b></div>'
        '<div><span class="k">XIRR</span><b>%s</b></div>'
        '<div><span class="k">期数</span><b>%d 笔</b></div>'
        '<div><span class="k">申购费率</span><b>%.2f%%</b></div>'
        '</div></div>'
        '<div class="sub" style="margin:14px 0 8px">%s</div>'
        '<div class="scrollbox"><table><thead><tr><th>日期</th><th class="num">谷底分</th><th class="num">投入</th>'
        '<th class="num">复权净值</th><th class="num">累计投入</th>'
        '<th class="num">累计市值</th><th class="num">方式</th></tr></thead>'
        '<tbody>%s</tbody></table></div>'
        % (format(res["dca_amount"], ","), formula,
           format(int(ledger["invested"]), ","),
           format(int(round(ledger["value"])), ","),
           pnl_color, ("%+d" % ledger["pnl"]), ("%+.2f%%" % (ledger["pnl_pct"] * 100)),
           ledger.get("fee_total", 0.0),
           ledger["cost"], xirr_txt, ledger["n"],
           float(cfg["dca"].get("fee_rate", 0.0)) * 100.0,
           note, rows_html))


def trough_rows_html(tro):
    """谷底分的三因子拆解表。"""
    rows = [
        ("回撤深度", "距一年高点 <b>%.0f</b> 分" % tro["D"], tro["D"], "60%",
         "离一年高点的跌幅 ÷ 15%，封顶 100"),
        ("三年位置", "近三年区间 <b>%.0f</b> 分" % tro["A"], tro["A"], "25%",
         "价格在三年区间的位置取反"),
        ("利差位置", "股息率−10Y <b>%.0f</b> 分" % tro["E"], tro["E"], "15%",
         "股债利差在过去三年的分位"),
    ]
    out = []
    for name, val, score, weight, desc in rows:
        out.append(
            '<tr><td>%s</td><td class="num">%s</td>'
            '<td><div class="track"><i style="width:%.0f%%;background:#38bdf8"></i></div>'
            '<span class="muted">%.0f</span></td>'
            '<td class="num">%s</td><td class="desc">%s</td></tr>'
            % (name, val, score, score, weight, desc))
    return "\n".join(out)


def render(res, rows, cfg, ledger=None, tro=None, tro_series=None):
    if tro:
        color, bg, action, hint = trough_band(res["total"])
    else:
        color, bg, action, hint = band(res["total"])
    prev = None
    for r in rows[:-1]:
        if str(r.get("total", "")).isdigit():
            prev = int(r["total"])
    delta_html = ""
    if prev is not None:
        d = res["total"] - prev
        if d:
            delta_html = '<span class="delta">较上次 %s%d</span>' % (
                "+" if d > 0 else "", d)
        else:
            delta_html = '<span class="delta">与上次持平</span>'

    if tro_series:
        from trough import band as _tband
        history_html = "\n".join(
            '<tr><td>%s</td><td class="num">%.3f</td>'
            '<td class="num strong" style="color:%s">%.0f</td>'
            '<td class="num">%s</td><td class="num">%.0f</td><td class="num">%.0f</td></tr>' % (
                r["date"], r["price"], _tband(r["score"])[2], r["score"],
                _tband(r["score"])[3], r["D"], r["A"])
            for r in reversed(tro_series[-60:]))
    else:
        history_html = "\n".join(
            '<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
            '<td class="num">%s</td><td class="num">%s</td>'
            '<td class="num strong" style="color:%s">%s</td></tr>' % (
                r.get("date", ""), r.get("price", ""), r.get("spread_pct", ""),
                r.get("rsi14", ""), r.get("div", ""),
                band(int(r["total"]))[0] if str(r.get("total", "")).isdigit() else "#94a3b8",
                r.get("total", ""))
            for r in reversed(rows))

    defaults = {f["key"]: f["value"] for f in res["factors"]}
    inputs = ""
    for key, label in (("spread", "利差分位 %"), ("div", "股息率 %"),
                       ("rsi", "RSI14"), ("bias", "年线BIAS %"), ("env", "市场情绪")):
        raw = defaults[key].replace("%", "").replace("+", "")
        inputs += ('<label>%s<input id="in-%s" type="number" step="0.1" value="%s"></label>'
                   % (label, key, raw))

    with open(os.path.join(BASE_DIR, "template.html"), "r", encoding="utf-8") as f:
        tpl = f.read()

    rep = {
        "__COLOR__": color, "__BGC__": bg, "__SCORE__": str(res["total"]),
        "__ACTION__": action, "__HINT__": hint, "__DATE__": res["date"],
        "__PRICE__": fmt(res["price"], 3), "__GEN__": res["generated"],
        "__DATA_LINE__": (
            '即时 <b>%s %s</b> · 现价 <b>%s</b>'
            % (res["date"], res["quote_time"], fmt(res["price"], 3))
            if res.get("intraday") else
            '数据日 <b>%s</b>（最近收盘日） · 收盘 <b>%s</b>'
            % (res["date"], fmt(res["price"], 3))),
        "__DELTA__": delta_html,
        "__ROWS__": (trough_rows_html(tro) if tro else build_rows_html(res)),
        "__SPARK__": spark_svg(rows), "__HIST__": history_html,
        "__MA250__": fmt(res["ma250"], 3), "__MA250_GAP__": "%+.1f%%" % res["bias"],
        "__DIV__": fmt(res["div"], 2), "__Y10__": fmt(res["y10"], 2),
        "__Y10_DATE__": res["y10_date"], "__SPREAD__": fmt(res["spread"], 2),
        "__SPREADPCT__": "%.0f" % res["spread_pct"],
        "__PE__": fmt(res["pe"], 2), "__PEPCT__": "%.0f" % res["pe_pct"],
        "__DIVPCT__": "%.0f" % res["div_pct"], "__RSI__": "%.1f" % (res["rsi14"] or 0),
        "__MOM60__": ("%+.1f%%" % res["mom60"]) if res["mom60"] is not None else "—",
        "__MOM300__": ("%+.1f%%" % res["mom60_300"]) if res["mom60_300"] is not None else "—",
        "__RS60__": ("%+.1f%%" % res["rs60"]) if res["rs60"] is not None else "—",
        "__ENV__": "%.0f" % res["env"], "__INDEX__": res["index_name"],
        "__DCA__": format(res["dca_amount"], ","),
        "__DCA_BLOCK__": ledger_block(res, cfg, ledger),
        "__CHART_JSON__": json.dumps([[r["date"], round(r["price"], 4), round(r["score"], 1)]
                                       for r in (tro_series or [])], ensure_ascii=False),
        "__TRO_SCORE__": ("%.0f" % tro["score"]) if tro else "—",
        "__TRO_BAND__": tro["band"] if tro else "—",
        "__TRO_COLOR__": tro["color"] if tro else "#94a3b8",
        "__TRO_PREV__": ("%.0f" % tro["prev20"]) if tro else "—",
        "__TRO_D__": ("%.0f" % tro["D"]) if tro else "—",
        "__TRO_A__": ("%.0f" % tro["A"]) if tro else "—",
        "__TRO_E__": ("%.0f" % tro["E"]) if tro else "—",
        "__N__": str(res["spreads_n"]),
        "__W_SPREAD__": str(cfg["weights"]["spread"]),
        "__W_DIV__": str(cfg["weights"]["div"]),
        "__W_RSI__": str(cfg["weights"]["rsi"]),
        "__W_BIAS__": str(cfg["weights"]["bias"]),
        "__W_ENV__": str(cfg["weights"]["env"]),
        "__INPUTS__": inputs,
        "__BANDS__": ("0-20 极度低估（重仓） / 21-40 偏冷（建仓） / 41-60 中性（观望） / "
                      "61-80 偏热（止盈） / 81-100 极度高估（清仓）"),
        "__WEIGHTS_JS__": json.dumps(cfg["weights"]),
        "__RANGES_JS__": json.dumps(cfg["ranges"]),
        "__PERCENTILE_YEARS__": str(cfg.get("percentile_years", 10)),
    }
    for k, v in rep.items():
        tpl = tpl.replace(k, v)
    return tpl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-copy", action="store_true", help="不复制到桌面")
    ap.add_argument("--open", action="store_true", help="生成后用默认浏览器打开")
    ap.add_argument("--out", default=os.path.join(BASE_DIR, "report.html"))
    args = ap.parse_args()

    with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
        cfg = json.load(f)

    print("开始取数（正常 5–10 秒，网络慢时会打印进度）…", flush=True)
    set_deadline(90)
    try:
        frames = load_frames(cfg)
    except Exception as e:                    # noqa: BLE001
        print("[失败] 取数失败：%s" % e)
        print("      旧报告没有被覆盖，过几分钟再双击一次即可。")
        return 1
    res = compute(cfg, frames)

    # 谷底分取代温度分：先算谷底分，再让它成为主分数
    tro = None
    tro_rows = []
    score_map = None
    try:
        import trough
        tro_rows = trough.build(frames)
        tro = trough.summary(tro_rows)
        score_map = {r["date"]: r["score"] for r in tro_rows}
        res["total"] = tro["score"]
        adj = frames["nav_adj"]
        ma20 = {}
        for _i in range(19, len(adj)):
            ma20[adj[_i][0]] = sum(p for _, p in adj[_i - 19:_i + 1]) / 20.0
        gap_map = {}
        for _r in tro_rows:
            _m = ma20.get(_r["date"])
            if _m:
                gap_map[_r["date"]] = (_m / _r["price"] - 1) * 100
        res["gap"] = gap_map.get(res["date"])
        res["dca_amount"] = dca_amount(res["total"], cfg, res["gap"])
        print("     谷底分 %.0f（%s）· 20 个交易日前 %.0f" % (tro["score"], tro["band"], tro["prev20"]))
    except Exception as e:                    # noqa: BLE001
        print("[WARN] 谷底分计算失败: %s" % e)

    rows = save_history(os.path.join(BASE_DIR, "history.csv"), res)

    ledger = None
    try:
        import dca_core                      # 延迟导入，避免循环依赖
        ledger = dca_core.build_ledger(cfg, frames=frames, score_map=score_map,
                                       mirror=True, gap_map=gap_map)
    except Exception as e:                    # noqa: BLE001
        print("[WARN] 定投账本生成失败: %s" % e)

    html = render(res, rows, cfg, ledger, tro, tro_rows)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    with open(os.path.join(BASE_DIR, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    print("[OK] %s 收盘 %.3f  谷底分 %d  %s" % (
        res["date"], res["price"], res["total"],
        (trough_band(res["total"]) if tro else band(res["total"]))[2]))
    print("     利差分位 %.0f%% | 股息率 %.2f%% | 10Y %.2f%% | 利差 %.2f%% | "
          "RSI %.1f | BIAS %+.1f%% | 情绪 %.0f" % (
              res["spread_pct"], res["div"], res["y10"], res["spread"],
              res["rsi14"] or 0, res["bias"], res["env"]))

    dst = cfg.get("desktop_copy")
    copied = False
    if dst and not args.no_copy:
        try:
            with open(dst, "w", encoding="utf-8") as f:
                f.write(html)
            copied = True
            print("[OK] 已复制到 %s" % dst)
        except Exception as e:      # noqa: BLE001
            print("[WARN] 复制到桌面失败: %s" % e)

    if args.open:
        target = dst if copied else args.out
        try:
            os.startfile(target)    # noqa: S606 - 仅打开本地生成的报告
        except Exception as e:      # noqa: BLE001
            print("[WARN] 打开报告失败: %s" % e)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
