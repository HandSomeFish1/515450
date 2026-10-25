# -*- coding: utf-8 -*-
"""515450 收盘曲线 + 触发日偏离标注（可左右拖动）"""
import json

from PIL import Image, ImageDraw, ImageFont

import daily_score as ds
import trough

cfg = json.load(open("config.json", encoding="utf-8"))
frames = ds.load_frames(cfg)
adj = frames["nav_adj"]
ma20 = {}
for i in range(19, len(adj)):
    ma20[adj[i][0]] = sum(p for _, p in adj[i - 19:i + 1]) / 20.0

rows = [r for r in trough.build(frames) if r["date"] >= "2023-10-01"]
pts = []
for r in rows:
    m = ma20.get(r["date"])
    gap = None
    if m and r["score"] >= 75:
        g = (m / r["price"] - 1) * 100
        if g > 0:
            gap = round(g, 1)
    pts.append([r["date"], round(r["price"], 4), gap, 1 if r["score"] >= 75 else 0])

payload = json.dumps(pts, ensure_ascii=False, separators=(",", ":"))
json.dump(pts, open("price_gap_pts.json", "w", encoding="utf-8"), ensure_ascii=False)
n = len(pts)
hits = sum(1 for p in pts if p[2] is not None)
print("点数 %d，触发日 %d" % (n, hits))

html = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>515450 收盘曲线 · 触发日偏离</title>
<style>
 body{margin:0;padding:24px 16px 40px;background:#080d16;color:#e7eef9;
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,sans-serif;
      font-variant-numeric:tabular-nums}
 .wrap{max-width:1180px;margin:0 auto}
 h1{font-size:1.25rem;margin:0 0 4px}
 .sub{color:#8b9cb6;font-size:.8rem;margin-bottom:14px}
 .card{background:linear-gradient(180deg,rgba(255,255,255,.03),rgba(255,255,255,0)) #111a2b;
       border:1px solid #22304a;border-radius:16px;padding:16px}
 .bar{display:flex;justify-content:space-between;align-items:center;gap:12px;
      margin-bottom:10px;flex-wrap:wrap}
 .legend{display:flex;gap:16px;flex-wrap:wrap;font-size:.74rem;color:#8b9cb6}
 .legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}
 .hint{font-size:.72rem;color:#5b6b85}
 .scroller{overflow-x:auto;overflow-y:hidden;cursor:grab;border-radius:10px;
           border:1px solid #1b2740;background:#0b1424;padding-bottom:6px}
 .scroller.drag{cursor:grabbing}
 .scroller::-webkit-scrollbar{height:10px}
 .scroller::-webkit-scrollbar-thumb{background:#2a3a58;border-radius:99px}
 .scroller::-webkit-scrollbar-track{background:transparent}
 svg{display:block}
 .tip{position:fixed;display:none;pointer-events:none;background:#0b1424;border:1px solid #38bdf8;
      border-radius:8px;padding:6px 10px;font-size:.76rem;line-height:1.5;color:#e7eef9;
      box-shadow:0 8px 20px rgba(0,0,0,.5);z-index:9;white-space:nowrap}
 .tip b{color:#7dd3fc}
</style></head><body><div class="wrap">
<h1>515450 收盘曲线 · 谷底分 ≥ 75 且跌破 20 日线的日子</h1>
<div class="sub">2023-10-09 ~ 2026-10-23 · 共 __N__ 个交易日 · 触发 __HITS__ 天（数字＝MA20 比收盘价高的百分比）</div>

<div class="card">
  <div class="bar">
    <div class="legend">
      <span><i style="background:#38bdf8"></i>收盘价（复权）</span>
      <span><i style="background:#ef4444"></i>谷底分 ≥ 75 的当天</span>
      <span><i style="background:#22c55e"></i>谷底分 ≥ 75 且 MA20 &gt; 收盘（带数字）</span>
    </div>
    <div class="hint">按住鼠标左右拖动即可查看 · 也可以滚底部滚动条</div>
  </div>
  <div class="scroller" id="scroller">
    <div id="chart"></div>
  </div>
</div>
<div class="tip" id="tip"></div>
</div>

<script>
var DATA = __DATA__;
var DAY = 11, H = 430, L = 54, R = 24, T = 54, B = 46;
var n = DATA.length;
var W = L + R + n * DAY;

var closes = DATA.map(function(d){return d[1];});
var mn = Math.min.apply(null, closes), mx = Math.max.apply(null, closes);
var pad = (mx - mn) * 0.12;
mn -= pad; mx += pad;

function X(i){ return L + i * DAY + DAY/2; }
function Y(v){ return H - B - (v - mn)/(mx - mn) * (H - T - B); }

var s = '<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'">';

// 网格
for (var g = 0; g <= 4; g++){
  var val = mn + (mx - mn) * g / 4, y = Y(val);
  s += '<line x1="'+L+'" y1="'+y.toFixed(1)+'" x2="'+(W-R)+'" y2="'+y.toFixed(1)+'" stroke="#1b2740"/>';
  s += '<text x="'+(L-8)+'" y="'+(y+4).toFixed(1)+'" fill="#6b7d98" font-size="11" text-anchor="end">'+val.toFixed(3)+'</text>';
}

// 折线
var dstr = DATA.map(function(d,i){ return X(i).toFixed(1)+','+Y(d[1]).toFixed(1); }).join(' ');
s += '<polyline points="'+dstr+'" fill="none" stroke="#38bdf8" stroke-width="1.8"/>';

// 谷底分 ≥ 75 的点一律标红
DATA.forEach(function(d,i){
  if (!d[3]) return;
  s += '<circle cx="'+X(i).toFixed(1)+'" cy="'+Y(d[1]).toFixed(1)+'" r="2.9" fill="#ef4444"/>';
});

// 触发点（谷底分≥75 且 MA20>收盘）+ 数字
var lastLabelX = -999;
DATA.forEach(function(d,i){
  if (d[2] === null) return;
  var x = X(i), y = Y(d[1]);
  s += '<line x1="'+x.toFixed(1)+'" y1="'+(y+7).toFixed(1)+'" x2="'+x.toFixed(1)+'" y2="'+(y-26).toFixed(1)+'" stroke="#22c55e" stroke-width="1" opacity=".55"/>';
  s += '<circle cx="'+x.toFixed(1)+'" cy="'+y.toFixed(1)+'" r="3.4" fill="#22c55e"/>';
  var ly = (x - lastLabelX < 26) ? y - 34 : y - 20;
  s += '<text x="'+x.toFixed(1)+'" y="'+ly.toFixed(1)+'" fill="#7ee2a8" font-size="11" text-anchor="middle">'+d[2].toFixed(1)+'</text>';
  lastLabelX = x;
});

// 月份刻度
var lastMonth = '';
DATA.forEach(function(d,i){
  var m = d[0].slice(0,7);
  if (m !== lastMonth){
    lastMonth = m;
    var x = X(i);
    s += '<line x1="'+x.toFixed(1)+'" y1="'+(H-B)+'" x2="'+x.toFixed(1)+'" y2="'+(H-B+6)+'" stroke="#2a3a58"/>';
    s += '<text x="'+x.toFixed(1)+'" y="'+(H-B+20)+'" fill="#6b7d98" font-size="10" text-anchor="middle">'+m.slice(2)+'</text>';
  }
});
s += '</svg>';
document.getElementById("chart").innerHTML = s;

// 拖动
var sc = document.getElementById("scroller");
var down=false, startX=0, startLeft=0, moved=false;
sc.addEventListener("mousedown", function(e){
  down=true; moved=false; startX=e.pageX; startLeft=sc.scrollLeft; sc.classList.add("drag");
});
window.addEventListener("mouseup", function(){ down=false; sc.classList.remove("drag"); });
window.addEventListener("mousemove", function(e){
  if(!down) return;
  var dx = e.pageX - startX;
  if (Math.abs(dx) > 3) moved = true;
  sc.scrollLeft = startLeft - dx;
  if (moved) e.preventDefault();
});

// 悬停
var tip = document.getElementById("tip");
document.getElementById("chart").addEventListener("mousemove", function(e){
  if (down) { tip.style.display="none"; return; }
  var rect = this.getBoundingClientRect();
  var x = e.clientX - rect.left;
  var i = Math.round((x - L - DAY/2) / DAY);
  if (i < 0 || i >= n) { tip.style.display="none"; return; }
  var d = DATA[i];
  tip.style.display = "block";
  tip.style.left = (e.clientX + 14) + "px";
  tip.style.top = (e.clientY - 46) + "px";
  tip.innerHTML = "<b>" + d[0] + "</b><br>收盘 " + d[1].toFixed(3) +
    (d[2] === null ? "" : "<br>MA20 高 " + d[2].toFixed(1) + "%");
});
document.getElementById("chart").addEventListener("mouseleave", function(){ tip.style.display="none"; });

sc.scrollLeft = sc.scrollWidth;   // 默认滚到最右（最新）
</script>
</body></html>"""

html = (html.replace("__DATA__", payload)
            .replace("__N__", str(n))
            .replace("__HITS__", str(hits)))
open("price_gap.html", "w", encoding="utf-8").write(html)
print("已生成 price_gap.html（宽度 %d px）" % (54 + 24 + n * 11))

