# -*- coding: utf-8 -*-
"""谷底分 ≤ 75 时，MA20 高于收盘价的幅度分布（0.5% 一档）"""
import collections
import json

import daily_score as ds
import trough

cfg = json.load(open("config.json", encoding="utf-8"))
frames = ds.load_frames(cfg)
adj = frames["nav_adj"]
ma20 = {}
for i in range(19, len(adj)):
    ma20[adj[i][0]] = sum(p for _, p in adj[i - 19:i + 1]) / 20.0

rows = [r for r in trough.build(frames) if r["date"] >= "2023-10-01" and r["score"] <= 75]
gaps = []
for r in rows:
    m = ma20.get(r["date"])
    if m:
        gaps.append((m / r["price"] - 1) * 100)

lo = int(min(gaps) * 2) / 2.0 - 0.5
hi = int(max(gaps) * 2) / 2.0 + 0.5
bins = collections.Counter()
edges = []
x = lo
while x < hi + 0.001:
    edges.append(round(x, 1))
    x += 0.5

for g in gaps:
    idx = int((g - lo) // 0.5)
    idx = max(0, min(len(edges) - 1, idx))
    bins[edges[idx]] += 1

data = [[e, bins.get(e, 0)] for e in edges]
n = len(gaps)
pos = sum(1 for g in gaps if g > 0)
mean = sum(gaps) / n
srt = sorted(gaps)
median = srt[n // 2]

payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

page = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MA20 高于收盘价的幅度分布</title>
<style>
 body{margin:0;padding:24px 16px 40px;background:#080d16;color:#e7eef9;
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,sans-serif;
      font-variant-numeric:tabular-nums}
 .wrap{max-width:960px;margin:0 auto}
 h1{font-size:1.25rem;margin:0 0 4px}
 .sub{color:#8b9cb6;font-size:.8rem;margin-bottom:16px}
 .card{background:linear-gradient(180deg,rgba(255,255,255,.03),rgba(255,255,255,0)) #111a2b;
       border:1px solid #22304a;border-radius:16px;padding:18px;margin-bottom:14px}
 .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-bottom:14px}
 .m{background:#0d1522;border:1px solid #22304a;border-radius:10px;padding:9px 13px}
 .m .k{font-size:.68rem;color:#8b9cb6;display:block}
 .m .v{font-size:1.02rem;font-weight:650;margin-top:3px}
 .chartwrap{position:relative}
 .chart{width:100%;height:auto;display:block}
 .tip{position:absolute;display:none;pointer-events:none;background:#0b1424;border:1px solid #38bdf8;
      border-radius:8px;padding:6px 10px;font-size:.76rem;line-height:1.5;color:#e7eef9;
      transform:translate(-50%,-115%);white-space:nowrap;box-shadow:0 8px 20px rgba(0,0,0,.5);z-index:5}
 .tip b{color:#7dd3fc}
 .legend{display:flex;gap:16px;flex-wrap:wrap;font-size:.74rem;color:#8b9cb6;margin-bottom:8px}
 .legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}
 .note{color:#5b6b85;font-size:.74rem;line-height:1.7;margin-top:10px}
</style></head><body><div class="wrap">
<h1>MA20 高于收盘价的幅度分布</h1>
<div class="sub">2023-10-09 ~ 2026-10-23 · 只统计谷底分 ≤ 75 的交易日 · 每 0.5% 一档</div>

<div class="card">
  <div class="metrics">
    <div class="m"><div class="k">样本天数</div><div class="v">__N__ 天</div></div>
    <div class="m"><div class="k">均值</div><div class="v">__MEAN__%</div></div>
    <div class="m"><div class="k">中位数</div><div class="v">__MEDIAN__%</div></div>
    <div class="m"><div class="k">MA20 高于收盘</div><div class="v">__POS__%</div></div>
    <div class="m"><div class="k">最大</div><div class="v">__MAX__%</div></div>
  </div>
  <div class="legend">
    <span><i style="background:#4ade80"></i>负值区：收盘高于 MA20（价格在均线上方）</span>
    <span><i style="background:#f97316"></i>正值区：MA20 高于收盘（价格在均线下方）</span>
  </div>
  <div class="chartwrap" id="cwrap">
    <div id="chart"></div>
    <div class="tip" id="tip"></div>
  </div>
  <div class="note">横轴＝MA20 比收盘价高的百分比（0.5% 一档），纵轴＝符合条件的天数。
    左边（负值）是价格高过均线的日子，右边（正值）才是价格低于均线的日子。</div>
</div>
</div>
<script>
var DATA = __DATA__;
var W=900,H=380,L=52,R=20,T=18,B=64;
var maxC = Math.max.apply(null, DATA.map(function(d){return d[1];}));
var top = Math.ceil(maxC/10)*10;
var n = DATA.length;
var bw = (W-L-R)/n;

function X(i){ return L + i*bw; }
function Y(v){ return H-B - v/top*(H-T-B); }

var s='<svg viewBox="0 0 '+W+' '+H+'" class="chart">';
for(var v=0; v<=top; v+=10){
  s+='<line x1="'+L+'" y1="'+Y(v)+'" x2="'+(W-R)+'" y2="'+Y(v)+'" stroke="#22304a"/>';
  s+='<text x="'+(L-8)+'" y="'+(Y(v)+3)+'" fill="#6b7d98" font-size="10" text-anchor="end">'+v+'</text>';
}
DATA.forEach(function(d,i){
  var h = H-B - Y(d[1]);
  var c = d[0] < 0 ? "#4ade80" : "#f97316";
  s+='<rect x="'+(X(i)+1).toFixed(1)+'" y="'+Y(d[1]).toFixed(1)+'" width="'+(bw-2).toFixed(1)+
     '" height="'+Math.max(0,h).toFixed(1)+'" fill="'+c+'" opacity=".85" rx="2" data-i="'+i+'"/>';
});
s+='<text x="'+((L+W-R)/2)+'" y="'+(H-24)+'" fill="#6b7d98" font-size="11" text-anchor="middle">MA20 高于收盘价的幅度（%）</text>';
DATA.forEach(function(d,i){
  if(i % 4 === 0 || i === n-1){
    s+='<text x="'+(X(i)+bw/2).toFixed(1)+'" y="'+(H-8)+'" fill="#8b9cb6" font-size="10" text-anchor="middle">'+
       (d[0]>0?"+":"")+d[0].toFixed(1)+'%</text>';
  }
});
s+='</svg>';
document.getElementById("chart").innerHTML=s;

var wrap=document.getElementById("cwrap"), tip=document.getElementById("tip");
wrap.addEventListener("mousemove", function(e){
  var t=e.target;
  if(t.tagName!=="rect"){ tip.style.display="none"; return; }
  var i=parseInt(t.getAttribute("data-i"),10), d=DATA[i];
  var total=DATA.reduce(function(a,b){return a+b[1];},0);
  var pct=(100*d[1]/total).toFixed(1);
  tip.style.display="block";
  tip.style.left=Math.min(86,Math.max(10,(X(i)+bw/2)/W*100))+"%";
  tip.style.top=(Y(d[1])/H*100)+"%";
  tip.innerHTML="<b>"+(d[0]>0?"+":"")+d[0].toFixed(1)+"% ~ "+(d[0]+0.5>0?"+":"")+(d[0]+0.5).toFixed(1)+
                "%</b><br>"+d[1]+" 天（"+pct+"%）";
});
wrap.addEventListener("mouseleave", function(){ tip.style.display="none"; });
</script>
</body></html>"""

html = (page.replace("__DATA__", payload)
            .replace("__N__", str(n))
            .replace("__MEAN__", "%+.2f" % mean)
            .replace("__MEDIAN__", "%+.2f" % median)
            .replace("__POS__", "%.0f" % (100.0 * pos / n))
            .replace("__MAX__", "%+.1f" % max(gaps)))
open("gap_hist.html", "w", encoding="utf-8").write(html)
json.dump({"bins": data, "n": n, "mean": mean, "median": median, "pos": pos, "max": max(gaps)},
          open("gap_hist.json", "w", encoding="utf-8"), ensure_ascii=False)
print("天数 %d，均值 %+.2f%%，中位数 %+.2f%%，最大 %+.2f%%，MA20 高于收盘占 %.0f%%" % (
    n, mean, median, max(gaps), 100.0 * pos / n))
print("已生成 gap_hist.html")
