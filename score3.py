# -*- coding: utf-8 -*-
"""515450 谷底分（温度 3.0）：设计 + 回测 + 曲线图

分数 = 过去 750 个交易日内，下面这个「便宜度」的分位（0-100）：
       便宜度 = 0.60×回撤深度 + 0.25×三年位置 + 0.15×利差位置
分数越高 = 越接近可买区域。
"""
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


dates = [d for d, _ in adj]
px = [p for _, p in adj]
n = len(dates)

rsi = [None] * n
ag = al = 0.0
for i in range(1, n):
    ch = px[i] - px[i - 1]
    if i == 14:
        ag = sum(max(px[j] - px[j - 1], 0) for j in range(1, 15)) / 14
        al = sum(max(-(px[j] - px[j - 1]), 0) for j in range(1, 15)) / 14
        rsi[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    elif i > 14:
        ag = (ag * 13 + max(ch, 0)) / 14
        al = (al * 13 + max(-ch, 0)) / 14
        rsi[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def rank(seq, v):
    return sum(1 for x in seq if x <= v) / float(len(seq)) if seq else 0.5


rows = []
for i in range(750, n):
    d, p = dates[i], px[i]
    pos3 = rank(px[i - 749:i + 1], p)
    A = 100 * (1 - pos3)
    ma250 = sum(px[i - 249:i + 1]) / 250.0
    devs = [px[j] / (sum(px[j - 249:j + 1]) / 250.0) - 1 for j in range(i - 249, i + 1)]
    sd = st.pstdev(devs) or 1e-6
    z = ((p / ma250 - 1) - st.mean(devs)) / sd
    B = 50 - 25 * max(-2, min(2, z))
    r_hist = [x for x in rsi[i - 249:i + 1] if x is not None]
    C = 100 * (1 - rank(r_hist, rsi[i]))
    hi250 = max(px[i - 249:i + 1])
    D = 100 * min(1.0, abs(p / hi250 - 1) / 0.15)
    pe_now = asof(pe_dates, pe_d, d)
    y10 = asof(bond_dates, bond_d, d)
    if not pe_now or y10 is None:
        continue
    spread = 100.0 * payout / pe_now - y10
    sp_hist = []
    for j in range(i - 749, i + 1):
        pj = asof(pe_dates, pe_d, dates[j])
        yj = asof(bond_dates, bond_d, dates[j])
        if pj and yj:
            sp_hist.append(100.0 * payout / pj - yj)
    E = 100 * rank(sp_hist, spread)
    rows.append(dict(date=d, price=p, A=A, B=B, C=C, D=D, E=E))

RAW = [0.60 * r["D"] + 0.25 * r["A"] + 0.15 * r["E"] for r in rows]
score = []
for i in range(len(RAW)):
    w = RAW[max(0, i - 749):i + 1]
    score.append(100.0 * sum(1 for x in w if x <= RAW[i]) / len(w))

dates = [r["date"] for r in rows]
px = [r["price"] for r in rows]
n = len(rows)


def ranks(x):
    o = sorted(range(len(x)), key=lambda i: x[i])
    r = [0] * len(x)
    for pos, i in enumerate(o):
        r[i] = pos + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else 0.0


CORR = {}
print("样本 %s ~ %s，%d 天" % (dates[0], dates[-1], n))
for h in (20, 60, 120):
    CORR[h] = spearman([score[i] for i in range(n - h)],
                       [px[i + h] / px[i] - 1 for i in range(n - h)])
    print("  前 %3d 日收益 vs 谷底分：Spearman %+.3f" % (h, CORR[h]))
cross = sum(1 for i in range(1, n) if (score[i - 1] - 50) * (score[i] - 50) < 0)
print("  穿 50：%d 次；均值 %.0f；>80 的天数 %d" % (
    cross, st.mean(score), sum(1 for v in score if v > 80)))

print("\n分档（后 60 日）：")
for lo, hi in ((0, 20), (20, 40), (40, 60), (60, 80), (80, 100)):
    sel = [i for i in range(n - 60) if lo <= score[i] < hi]
    if not sel:
        continue
    rets = [px[i + 60] / px[i] - 1 for i in sel]
    print("  %3d-%3d: %4d 天，均 %+.2f%%，正收益 %.0f%%" % (
        lo, hi, len(sel), st.mean(rets) * 100,
        100 * sum(1 for x in rets if x > 0) / len(rets)))

# ---------- 图 ----------
BANDS = [(0, 20, "#ef4444", "顶部区"), (20, 40, "#f97316", "偏热"),
         (40, 60, "#94a3b8", "中性"), (60, 80, "#4ade80", "偏冷"),
         (80, 100, "#22c55e", "谷底区")]


def color_of(v):
    for a, b, c, _ in BANDS:
        if v < b or b == 100:
            return c
    return BANDS[-1][2]


W, H, L, R, T = 900, 330, 46, 104, 16
xs = [L + i * (W - L - R) / (n - 1) for i in range(n)]
ys = [T + v / 100.0 * (H - T - 30) for v in score]
svg = ['<svg viewBox="0 0 %d %d" class="chart">' % (W, H)]
for a, b, c, name in BANDS:
    y1 = T + a / 100.0 * (H - T - 30)
    y2 = T + b / 100.0 * (H - T - 30)
    svg.append('<rect x="%d" y="%.1f" width="%d" height="%.1f" fill="%s" opacity=".07"/>'
               % (L, y1, W - L - R, y2 - y1, c))
    svg.append('<text x="%d" y="%.1f" fill="%s" font-size="10">%d–%d %s</text>'
               % (W - R + 6, (y1 + y2) / 2 + 3, c, a, b, name))
for v in (0, 20, 40, 60, 80, 100):
    y = T + v / 100.0 * (H - T - 30)
    svg.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#22304a"/>' % (L, y, W - R, y))
    svg.append('<text x="%d" y="%.1f" fill="#6b7d98" font-size="10" text-anchor="end">%d</text>'
               % (L - 8, y + 3, v))
for i in range(1, n):
    svg.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="2"/>'
               % (xs[i - 1], ys[i - 1], xs[i], ys[i], color_of((score[i - 1] + score[i]) / 2)))
for i in range(0, n, max(1, n // 10)):
    svg.append('<text x="%.1f" y="%d" fill="#6b7d98" font-size="10" text-anchor="middle">%s</text>'
               % (xs[i], H - 8, dates[i][:7]))
svg.append("</svg>")

PH = 150
pys = [PH - 24 - (p - min(px)) / (max(px) - min(px)) * (PH - 44) for p in px]
psvg = ['<svg viewBox="0 0 %d %d" class="chart">' % (W, PH)]
psvg.append('<polyline points="%s" fill="none" stroke="#38bdf8" stroke-width="1.6"/>'
            % " ".join("%.1f,%.1f" % (xs[i], pys[i]) for i in range(n)))
for i in range(0, n, max(1, n // 10)):
    psvg.append('<text x="%.1f" y="%d" fill="#6b7d98" font-size="10" text-anchor="middle">%s</text>'
                % (xs[i], PH - 6, dates[i][:7]))
psvg.append("</svg>")

cur = score[-1]
labels = ["顶部区", "偏热", "中性", "偏冷", "谷底区"]
page = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>515450 谷底分（温度 3.0）</title>
<style>
 body{margin:0;padding:26px 18px;background:#080d16;color:#e7eef9;
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,sans-serif;
      font-variant-numeric:tabular-nums}
 .wrap{max-width:960px;margin:0 auto}
 h1{font-size:1.3rem;margin:0 0 6px}
 .sub{color:#8b9cb6;font-size:.82rem;margin-bottom:16px}
 .card{background:linear-gradient(180deg,rgba(255,255,255,.03),rgba(255,255,255,0)) #111a2b;
       border:1px solid #22304a;border-radius:18px;padding:18px;margin-bottom:16px}
 .score{font-size:3rem;font-weight:800;line-height:1;color:%(color)s}
 .pill{display:inline-block;margin-left:12px;padding:4px 14px;border-radius:999px;
       border:1px solid %(color)s;color:%(color)s;font-size:.85rem}
 .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin-top:14px}
 .m{background:#0d1522;border:1px solid #22304a;border-radius:12px;padding:10px 14px}
 .m .k{font-size:.7rem;color:#8b9cb6}
 .m .v{font-size:1.05rem;font-weight:650;margin-top:2px}
 .chart{width:100%%;height:auto;display:block}
 .note{color:#8b9cb6;font-size:.76rem;line-height:1.7;margin-top:10px}
 .legend{display:flex;gap:16px;flex-wrap:wrap;font-size:.76rem;color:#8b9cb6;margin-bottom:8px}
 .legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}
</style></head><body><div class="wrap">
<h1>515450 谷底分（温度 3.0）</h1>
<div class="sub">%(span)s · 分数越高越接近可买区域（纵向已翻转：越往下分数越高）</div>
<div class="card">
  <div><span class="score">%(cur).0f</span><span class="pill">%(name)s</span></div>
  <div class="metrics">
    <div class="m"><div class="k">后 60 日相关性</div><div class="v">%(corr)+.2f</div></div>
    <div class="m"><div class="k">穿 50 次数</div><div class="v">%(cross)d 次</div></div>
    <div class="m"><div class="k">>80 的天数</div><div class="v">%(hi)d 天</div></div>
    <div class="m"><div class="k">全样本均值</div><div class="v">%(avg).0f</div></div>
  </div>
</div>
<div class="card">
  <div class="legend">%(legend)s</div>
  %(chart)s
  <div class="note">分数 = 便宜度在近 750 个交易日里的分位；便宜度 = 0.60×回撤深度 + 0.25×三年位置 + 0.15×利差位置。</div>
</div>
<div class="card">
  <div class="note" style="margin:0 0 6px">对应净值：</div>
  %(price)s
</div>
</div></body></html>"""

legend = "".join('<span><i style="background:%s"></i>%d–%d %s</span>' % (c, a, b, nm)
                 for a, b, c, nm in BANDS)
with open("score3.html", "w", encoding="utf-8") as f:
    f.write(page % dict(color=color_of(cur), name=labels[min(4, int(cur // 20))],
                        span="%s ~ %s" % (dates[0], dates[-1]), cur=cur, corr=CORR[60],
                        cross=cross, hi=sum(1 for v in score if v > 80),
                        avg=st.mean(score), legend=legend, chart="".join(svg),
                        price="".join(psvg)))

with open("score3.csv", "w", encoding="utf-8-sig") as f:
    f.write("日期,净值,谷底分,回撤深度,三年位置,利差位置\n")
    for i, r in enumerate(rows):
        f.write("%s,%.4f,%.1f,%.1f,%.1f,%.1f\n" % (r["date"], r["price"], score[i],
                                                   r["D"], r["A"], r["E"]))
import json as _json
_json.dump([[r["date"], round(r["price"], 4), round(score[i], 1)] for i, r in enumerate(rows)],
           open("score_series.json", "w", encoding="utf-8"), ensure_ascii=False)

print("\n当前：%s 谷底分 %.0f（%s）" % (dates[-1], cur, labels[min(4, int(cur // 20))]))
print("已生成 score3.html / score3.csv")
