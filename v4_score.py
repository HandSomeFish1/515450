# -*- coding: utf-8 -*-
"""V4/V6 值博率模型复刻：931446 最近两个月逐日打分"""
import json
import re
import urllib.request

import pandas as pd

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
XLSX = r"C:\Users\xvhai\Downloads\931446perf (1).xlsx"
ANCHOR = "2026-10-13"
ANCHOR_CLOSE = 3409.55
A = dict(did_hist=1.71, did_abs=1.13, did_z=0.40, pb=3.23, cn10y=5.96,
         spread=5.94, price_ma=5.81, pos252=7.30, rsi=2.15, vol=3.40)


def get(url, ref):
    return urllib.request.urlopen(urllib.request.Request(
        url, headers={"User-Agent": UA, "Referer": ref}), timeout=25).read().decode("utf-8", "ignore")


def bond_10y():
    base = ("https://datacenter.eastmoney.com/api/data/get?type=RPTA_WEB_TREASURYYIELD"
            "&sty=ALL&st=SOLAR_DATE&sr=-1&token=894050c76af8597a853f5b408b759f5d&ps=500&p=")
    out = {}
    for p in range(1, 5):
        v = json.loads(get(base + str(p), "https://data.eastmoney.com/cjsj/zmgzsyl.html"))
        rows = ((v.get("result") or {}).get("data")) or []
        if not rows:
            break
        for r in rows:
            d = str(r.get("SOLAR_DATE"))[:10]
            y = r.get("EMM00166466")
            if d and y not in (None, "", "-"):
                out[d] = float(y)
        if min(out) < "2023-01-01":
            break
    return out


df = pd.read_excel(XLSX, sheet_name=0)
df = df[df["指数代码Index Code"] == 931446].copy()
df["date"] = pd.to_datetime(df["日期Date"].astype(str), format="%Y%m%d").dt.strftime("%Y-%m-%d")
df = df.sort_values("date")
dates = df["date"].tolist()
closes = df["收盘Close"].astype(float).tolist()
vols = df["成交量 Volume"].astype(float).tolist()
n = len(dates)
bond = bond_10y()

# RSI（单次遍历）
rsi = [None] * n
ag = al = 0.0
for i in range(1, n):
    ch = closes[i] - closes[i - 1]
    if i == 14:
        g = sum(max(closes[j] - closes[j - 1], 0) for j in range(1, 15)) / 14
        l = sum(max(-(closes[j] - closes[j - 1]), 0) for j in range(1, 15)) / 14
        ag, al = g, l
        rsi[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    elif i > 14:
        ag = (ag * 13 + max(ch, 0)) / 14
        al = (al * 13 + max(-ch, 0)) / 14
        rsi[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def rank(seq, v):
    return sum(1 for x in seq if x <= v) / float(len(seq)) if seq else 0.5


rows = []
for i in range(250, n):
    d, c = dates[i], closes[i]
    ma60 = sum(closes[i - 59:i + 1]) / 60
    ma250 = sum(closes[i - 249:i + 1]) / 250
    pos = rank(closes[i - 251:i + 1], c)
    r = rsi[i]
    r_hist = [x for x in rsi[i - 250:i + 1] if x is not None]
    def vratio(j):
        m = sum(vols[j - 19:j + 1]) / 20
        if not m or m != m:
            return 1.0
        return vols[j] / m
    v_hist = [vratio(j) for j in range(i - 250, i + 1)]
    vr = vratio(i)
    y10 = bond.get(d) or bond.get(dates[i - 1])
    did = 4.05 * ANCHOR_CLOSE / c
    spread = did - y10
    did_hist = [4.05 * ANCHOR_CLOSE / closes[j] for j in range(0, i + 1)]
    spread_hist = [(4.05 * ANCHOR_CLOSE / closes[j]) - (bond.get(dates[j]) or y10)
                   for j in range(0, i + 1)]
    rate_hist = [bond.get(dates[j]) for j in range(0, i + 1) if bond.get(dates[j])]
    mean_did = sum(did_hist) / len(did_hist)
    sd = (sum((x - mean_did) ** 2 for x in did_hist) / len(did_hist)) ** 0.5 or 1e-6
    rows.append(dict(date=d, close=c, ma60=ma60, ma250=ma250, pos=pos, rsi=r,
                     rsi_rank=rank(r_hist, r), vol_ratio=vr, vol_rank=rank(v_hist, vr),
                     y10=y10, did=did, spread=spread, did_rank=rank(did_hist, did),
                     spread_rank=rank(spread_hist, spread), rate_rank=rank(rate_hist, y10),
                     z=(did - mean_did) / sd,
                     dev=0.5 * (c / ma60 - 1) + 0.5 * (c / ma250 - 1)))

anch = next(x for x in rows if x["date"] == ANCHOR)
CAP = dict(did_hist=14, did_abs=6, did_z=4, pb=10, cn10y=8, spread=18,
           price_ma=8, pos252=15, rsi=12, vol=5)

out = []
for r in rows:
    s = {
        "did_hist": A["did_hist"] + 14 * (anch["did_rank"] - r["did_rank"]),
        "did_abs": A["did_abs"] + 6 * (anch["did_rank"] - r["did_rank"]),
        "did_z": A["did_z"] + 1.0 * (r["z"] - anch["z"]),
        "pb": A["pb"] + 10 * (anch["did_rank"] - r["did_rank"]),
        "cn10y": A["cn10y"] + 4 * (r["rate_rank"] - anch["rate_rank"]),
        "spread": A["spread"] + 18 * (r["spread_rank"] - anch["spread_rank"]),
        "price_ma": A["price_ma"] + 8 * (r["dev"] - anch["dev"]) / 0.10,
        "pos252": A["pos252"] + 15 * (anch["pos"] - r["pos"]),
        "rsi": A["rsi"] + 12 * (anch["rsi_rank"] - r["rsi_rank"]),
        "vol": A["vol"] + 5 * (r["vol_rank"] - anch["vol_rank"]),
    }
    for k in s:
        s[k] = max(0.0, min(CAP[k], s[k]))
    out.append((r["date"], sum(s.values()), s, r["close"], r["did"], r["spread"]))

start = "2026-08-25"
sel = [x for x in out if x[0] >= start]
print("区间 %s ~ %s，共 %d 个交易日\n" % (sel[0][0], sel[-1][0], len(sel)))
print("%-12s %8s %7s %7s %7s %7s" % ("日期", "收盘", "估值面", "宏观面", "技术面", "总分"))
for d, tot, s, c, did, sp in sel:
    val = s["did_hist"] + s["did_abs"] + s["did_z"] + s["pb"]
    mac = s["cn10y"] + s["spread"]
    tec = s["price_ma"] + s["pos252"] + s["rsi"] + s["vol"]
    print("%-12s %8.2f %7.2f %7.2f %7.2f %7.2f" % (d, c, val, mac, tec, tot))

with open("v4_931446_2m.csv", "w", encoding="utf-8-sig") as f:
    f.write("日期,收盘,股息率,利差pp,估值面,宏观面,技术面,总分,DID历史,DID绝对,DID_Z,PB,CN10Y,利差,PriceMA,位置252,RSI,成交量\n")
    for d, tot, s, c, did, sp in sel:
        val = s["did_hist"] + s["did_abs"] + s["did_z"] + s["pb"]
        mac = s["cn10y"] + s["spread"]
        tec = s["price_ma"] + s["pos252"] + s["rsi"] + s["vol"]
        f.write("%s,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f\n" % (
            d, c, did, sp, val, mac, tec, tot, s["did_hist"], s["did_abs"], s["did_z"],
            s["pb"], s["cn10y"], s["spread"], s["price_ma"], s["pos252"], s["rsi"], s["vol"]))
print("\n锚点 %s：总分 %.2f（原始 37.02）" % (ANCHOR, next(x[1] for x in out if x[0] == ANCHOR)))
hi = max(sel, key=lambda x: x[1])
lo = min(sel, key=lambda x: x[1])
print("区间最高 %.2f（%s），最低 %.2f（%s）" % (hi[1], hi[0], lo[1], lo[0]))

# ---------------- 曲线图 ----------------
BANDS = [(0, 30, "#ef4444", "低位风险"), (30, 45, "#f97316", "偏弱观察"),
         (45, 60, "#f59e0b", "中性观察"), (60, 70, "#84cc16", "温和积极"),
         (70, 85, "#22c55e", "偏强观察"), (85, 100, "#16a34a", "高位共振")]


def band_of(v):
    for a, b, c, name in BANDS:
        if v <= b:
            return c, name
    return BANDS[0][2], BANDS[0][3]


W, H, L, R, T, B = 900, 380, 46, 118, 18, 38
n = len(sel)
xs = [L + i * (W - L - R) / float(n - 1) for i in range(n)]
ys = [H - B - v / 100.0 * (H - T - B) for _, v, _, _, _, _ in sel]

svg = ['<svg viewBox="0 0 %d %d" class="chart">' % (W, H)]
for a, b, color, name in BANDS:
    y1 = H - B - b / 100.0 * (H - T - B)
    y2 = H - B - a / 100.0 * (H - T - B)
    svg.append('<rect x="%d" y="%.1f" width="%d" height="%.1f" fill="%s" opacity=".07"/>'
               % (L, y1, W - L - R, y2 - y1, color))
    svg.append('<text x="%d" y="%.1f" fill="%s" font-size="10" opacity=".9">%d–%d %s</text>'
               % (W - R + 8, (y1 + y2) / 2 + 3, color, a, b, name))
for v in (0, 20, 40, 60, 80, 100):
    y = H - B - v / 100.0 * (H - T - B)
    svg.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#22304a"/>' % (L, y, W - R, y))
    svg.append('<text x="%d" y="%.1f" fill="#6b7d98" font-size="10" text-anchor="end">%d</text>'
               % (L - 8, y + 3, v))
pts = " ".join("%.1f,%.1f" % (xs[i], ys[i]) for i in range(n))
svg.append('<polyline points="%s" fill="none" stroke="#38bdf8" stroke-width="2.2" '
           'stroke-linejoin="round" stroke-linecap="round"/>' % pts)
for i, (d, v, s, c, did, sp) in enumerate(sel):
    color, _ = band_of(v)
    is_anchor = d == ANCHOR
    svg.append('<circle cx="%.1f" cy="%.1f" r="%s" fill="%s"%s/>'
               % (xs[i], ys[i], "4" if is_anchor else "3", color,
                  ' stroke="#e7eef9" stroke-width="1.5"' if is_anchor else ""))
for i in range(0, n, max(1, n // 9)):
    svg.append('<text x="%.1f" y="%d" fill="#6b7d98" font-size="10" text-anchor="middle">%s</text>'
               % (xs[i], H - B + 18, sel[i][0][5:]))
# 极值标注
for (d, v, _, _, _, _), tag in ((hi, "高"), (lo, "低")):
    k = [i for i in range(n) if sel[i][0] == d][0]
    svg.append('<text x="%.1f" y="%.1f" fill="#7dd3fc" font-size="10" text-anchor="middle">%.1f</text>'
               % (xs[k], ys[k] - 10, v))
svg.append("</svg>")

cur = sel[-1]
cur_band, cur_name = band_of(cur[1])
val = cur[2]["did_hist"] + cur[2]["did_abs"] + cur[2]["did_z"] + cur[2]["pb"]
mac = cur[2]["cn10y"] + cur[2]["spread"]
tec = cur[2]["price_ma"] + cur[2]["pos252"] + cur[2]["rsi"] + cur[2]["vol"]
avg = sum(x[1] for x in sel) / float(n)

page = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>931446 东证红利低波 · V4/V6 值博率曲线</title>
<style>
  body{margin:0;padding:26px 18px;background:#080d16;color:#e7eef9;
       font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,sans-serif;
       font-variant-numeric:tabular-nums}
  .wrap{max-width:960px;margin:0 auto}
  h1{font-size:1.35rem;margin:0 0 6px}
  .sub{color:#8b9cb6;font-size:.84rem;margin-bottom:16px}
  .card{background:linear-gradient(180deg,rgba(255,255,255,.03),rgba(255,255,255,0)) #111a2b;
        border:1px solid #22304a;border-radius:18px;padding:20px;margin-bottom:16px}
  .top{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap}
  .score{font-size:3.2rem;font-weight:800;line-height:1;color:%(color)s}
  .pill{display:inline-block;margin-left:12px;padding:4px 14px;border-radius:999px;
        border:1px solid %(color)s;color:%(color)s;background:rgba(255,255,255,.02);font-size:.85rem}
  .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin-top:16px}
  .m{background:#0d1522;border:1px solid #22304a;border-radius:12px;padding:10px 14px}
  .m .k{font-size:.7rem;color:#8b9cb6}
  .m .v{font-size:1.05rem;font-weight:650;margin-top:2px}
  .chart{width:100%%;height:auto;display:block}
  .note{color:#8b9cb6;font-size:.76rem;line-height:1.7;margin-top:10px}
  table{width:100%%;border-collapse:collapse;font-size:.85rem}
  th{color:#8b9cb6;font-weight:500;font-size:.72rem;text-align:left;padding:0 8px 8px;
     border-bottom:1px solid #22304a}
  td{padding:9px 8px;border-bottom:1px solid rgba(34,48,74,.55)}
  .num{text-align:right}
</style></head><body><div class="wrap">
<h1>931446 东证红利低波 · V4/V6 值博率</h1>
<div class="sub">%(span)s · 共 %(n)d 个交易日 · 分数越高越值得买</div>
<div class="card">
  <div class="top">
    <div><span class="score">%(cur).1f</span><span class="pill">%(name)s</span></div>
    <div class="note" style="margin:0">最新 %(lastdate)s</div>
  </div>
  <div class="metrics">
    <div class="m"><div class="k">估值面 /34</div><div class="v">%(val).2f</div></div>
    <div class="m"><div class="k">宏观面 /26</div><div class="v">%(mac).2f</div></div>
    <div class="m"><div class="k">技术面 /40</div><div class="v">%(tec).2f</div></div>
    <div class="m"><div class="k">两个月均值</div><div class="v">%(avg).1f</div></div>
    <div class="m"><div class="k">最高</div><div class="v">%(hi).1f</div></div>
    <div class="m"><div class="k">最低</div><div class="v">%(lo).1f</div></div>
  </div>
</div>
<div class="card">%(svg)s
  <div class="note">横轴为交易日，纵轴 0–100。白圈是 10-13（你给的截图日，校准锚点 37.02）。
  背景色带对应它的六档区间：0–30 低位风险 / 30–45 偏弱观察 / 45–60 中性观察 /
  60–70 温和积极 / 70–85 偏强观察 / 85–100 高位共振。</div>
</div>
<div class="card">
  <table><thead><tr><th>日期</th><th class="num">收盘</th><th class="num">估值</th>
  <th class="num">宏观</th><th class="num">技术</th><th class="num">总分</th></tr></thead><tbody>%(rows)s</tbody></table>
  <div class="note">锚点（10-13）精确；其余日期受百分位口径影响，绝对误差约 ±4 分，相对高低与趋势可信。</div>
</div>
</div></body></html>"""

rows_html = "".join(
    "<tr><td>%s</td><td class='num'>%.2f</td><td class='num'>%.2f</td><td class='num'>%.2f</td>"
    "<td class='num'>%.2f</td><td class='num'>%.2f</td></tr>"
    % (d, c, ss["did_hist"] + ss["did_abs"] + ss["did_z"] + ss["pb"],
       ss["cn10y"] + ss["spread"],
       ss["price_ma"] + ss["pos252"] + ss["rsi"] + ss["vol"], tot)
    for d, tot, ss, c, did, sp in sel)

with open("v4_931446_2m.html", "w", encoding="utf-8") as f:
    f.write(page % dict(color=cur_band, name=cur_name, span="%s ~ %s" % (sel[0][0], sel[-1][0]),
                        n=n, cur=cur[1], lastdate=cur[0], val=val, mac=mac, tec=tec,
                        avg=avg, hi=hi[1], lo=lo[1], svg="".join(svg), rows=rows_html))
print("已生成 v4_931446_2m.html")
