# -*- coding: utf-8 -*-
"""生成手机端单文件应用页（离线可用，支持手输股价试算）"""
import json
import os

import daily_score as ds
import trough

cfg = json.load(open("config.json", encoding="utf-8"))
frames = ds.load_frames(cfg)
adj = frames["nav_adj"]
ma20 = {}
for i in range(19, len(adj)):
    ma20[adj[i][0]] = sum(p for _, p in adj[i - 19:i + 1]) / 20.0

rows = trough.build(frames)
last = rows[-1]
gap = (ma20[last["date"]] / last["price"] - 1) * 100 if last["date"] in ma20 else None
score = last["score"]
if score < 20:
    amt, band_txt, color = 50, "顶部区", "#ef4444"
elif score < 75:
    amt, band_txt, color = 100, ("偏热" if score < 40 else "中性"), ("#f97316" if score < 40 else "#94a3b8")
else:
    amt, band_txt, color = 650, "谷底区" if score >= 80 else "偏冷", ("#22c55e" if score >= 80 else "#4ade80")
addon = 0
if score >= 75 and gap and gap > 3:
    addon = (gap - 3) * 880
    amt += addon

series = [[r["date"], round(r["price"], 4), round(r["score"], 1)] for r in rows[-260:]]
prev20 = rows[-21]["score"] if len(rows) > 21 else score

win = rows[-750:]
calc = {"p": [round(r["price"], 4) for r in win],
        "s": [round(r["spread"], 4) for r in win],
        "r": [round(r["raw"], 2) for r in win],
        "p0": round(last["price"], 4), "s0": round(last["spread"], 4)}

page = r"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#080d16">
<title>515450 谷底分</title>
<style>
  :root{--bg:#080d16;--card:#111a2b;--line:#22304a;--ink:#e7eef9;--muted:#8b9cb6;--dim:#5b6b85;--accent:#38bdf8}
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  body{margin:0;padding:16px 12px 40px;background:var(--bg);color:var(--ink);
       font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,sans-serif;
       font-variant-numeric:tabular-nums}
  .wrap{max-width:560px;margin:0 auto}
  h1{font-size:1.05rem;margin:0 0 2px;font-weight:700}
  .sub{color:var(--muted);font-size:.74rem;margin-bottom:14px}
  .card{background:linear-gradient(180deg,rgba(255,255,255,.03),rgba(255,255,255,0)) var(--card);
        border:1px solid var(--line);border-radius:16px;padding:16px;margin-bottom:12px}
  .top{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
  .score{font-size:3.2rem;font-weight:800;line-height:1}
  .pill{font-size:.78rem;padding:4px 12px;border-radius:999px;border:1px solid}
  .cap{color:var(--muted);font-size:.72rem;margin-top:6px}
  .metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}
  .m{background:#0d1522;border:1px solid var(--line);border-radius:10px;padding:8px 10px}
  .m .k{font-size:.62rem;color:var(--muted)}
  .m .v{font-size:.92rem;font-weight:650;margin-top:2px}
  .amt{font-size:2.2rem;font-weight:800;color:var(--accent);line-height:1}
  .formula{color:var(--muted);font-size:.76rem;margin-top:6px;line-height:1.5}
  .btns{display:flex;gap:6px;overflow-x:auto;padding-bottom:6px;margin-bottom:8px}
  .btns button{flex:0 0 auto;background:#0d1522;border:1px solid #2a3a58;color:#b8cbe4;
       border-radius:999px;padding:6px 14px;font-size:.74rem;font-family:inherit}
  .btns button.on{background:#1d4ed8;border-color:#3b82f6;color:#fff}
  .chartwrap{position:relative}
  .chart{width:100%;height:auto;display:block}
  .tip{position:absolute;display:none;pointer-events:none;background:#0b1424;border:1px solid var(--accent);
       border-radius:8px;padding:6px 9px;font-size:.72rem;line-height:1.45;color:var(--ink);
       transform:translate(-50%,-115%);white-space:nowrap;z-index:5}
  .tip b{color:#7dd3fc}
  .legend{display:flex;gap:10px;flex-wrap:wrap;font-size:.68rem;color:var(--muted);margin-bottom:6px}
  .legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px}
  .note{color:var(--dim);font-size:.7rem;line-height:1.65;margin-top:8px}
  .row{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid rgba(34,48,74,.5);
       font-size:.78rem}
  .row:last-child{border-bottom:none}
  .row .k{color:var(--muted)}
  .btn{width:100%;margin-top:12px;background:#1d4ed8;border:none;color:#fff;border-radius:12px;
       padding:12px;font-size:.9rem;font-family:inherit;font-weight:600}
  .mask{position:fixed;inset:0;background:rgba(3,7,14,.75);display:none;align-items:center;
        justify-content:center;padding:20px;z-index:50}
  .mask.on{display:flex}
  .modal{background:#111a2b;border:1px solid #2a3a58;border-radius:18px;padding:20px;width:100%;
         max-width:340px}
  .modal h3{margin:0 0 6px;font-size:1rem}
  .modal p{margin:0 0 14px;color:var(--muted);font-size:.74rem;line-height:1.5}
  .modal input{width:100%;background:#0d1522;border:1px solid #2a3a58;color:var(--ink);
        border-radius:10px;padding:12px;font-size:1.1rem;text-align:center;font-family:inherit}
  .modal .acts{display:flex;gap:10px;margin-top:14px}
  .modal .acts button{flex:1;padding:11px;border-radius:10px;font-size:.85rem;font-family:inherit;
        border:1px solid #2a3a58;background:#0d1522;color:#b8cbe4}
  .modal .acts button.go{background:#1d4ed8;border-color:#3b82f6;color:#fff;font-weight:600}
  .result{margin-top:12px;background:#0d1522;border:1px solid #2a3a58;border-radius:12px;padding:12px;
          display:none}
  .result.on{display:block}
  .result .big{font-size:1.6rem;font-weight:800}
  .result .line{color:var(--muted);font-size:.75rem;margin-top:4px;line-height:1.6}
</style></head><body><div class="wrap">

<h1>515450 红利低波 · 谷底分</h1>
<div class="sub">__DATE__ · 收盘 __PRICE____EST__</div>

<div class="card">
  <div class="top">
    <span class="score" style="color:__COLOR__">__SCORE__</span>
    <span class="pill" style="color:__COLOR__;border-color:__COLOR__">__BAND__</span>
  </div>
  <div class="cap">谷底分 / 100 · 20 个交易日前 __PREV__</div>
  <div class="metrics">
    <div class="m"><div class="k">回撤深度</div><div class="v">__D__</div></div>
    <div class="m"><div class="k">三年位置</div><div class="v">__A__</div></div>
    <div class="m"><div class="k">利差位置</div><div class="v">__E__</div></div>
  </div>
  <button class="btn" id="openCalc">手输股价试算</button>
  <div class="result" id="result"></div>
</div>

<div class="card">
  <div style="color:var(--muted);font-size:.72rem;margin-bottom:6px">今日定投</div>
  <div class="amt">¥__AMT__</div>
  <div class="formula">__FORMULA__</div>
</div>

<div class="card">
  <div class="btns" id="btns">
    <button data-n="21">1月</button>
    <button data-n="42" class="on">2月</button>
    <button data-n="63">3月</button>
    <button data-n="126">半年</button>
    <button data-n="250">1年</button>
    <button data-n="0">全部</button>
  </div>
  <div class="legend">
    <span><i style="background:#ef4444"></i>顶部</span>
    <span><i style="background:#f97316"></i>偏热</span>
    <span><i style="background:#94a3b8"></i>中性</span>
    <span><i style="background:#4ade80"></i>偏冷</span>
    <span><i style="background:#22c55e"></i>谷底</span>
  </div>
  <div class="chartwrap" id="cwrap">
    <div id="chart"></div>
    <div class="tip" id="tip"></div>
  </div>
  <div class="note">点一下曲线看当天数值；纵轴越往下越接近谷底。</div>
</div>

<div class="card">
  <div style="color:var(--muted);font-size:.72rem;margin-bottom:6px">规则</div>
  <div class="row"><span class="k">谷底分 &lt; 20</span><span>50 元</span></div>
  <div class="row"><span class="k">20 – 75</span><span>100 元</span></div>
  <div class="row"><span class="k">≥ 75</span><span>650 元</span></div>
  <div class="row"><span class="k">跌破 MA20 超 3%</span><span>每 1pp +880</span></div>
  <div class="note">数据截至 __DATE__，离线可用。</div>
</div>

</div>

<div class="mask" id="mask">
  <div class="modal">
    <h3>输入当前股价</h3>
    <p>按这个价格重算今天的谷底分和该投多少。默认填最新收盘 __PRICE__。</p>
    <input id="pxIn" type="number" step="0.001" inputmode="decimal" value="__PRICE__">
    <div class="acts">
      <button id="cancel">取消</button>
      <button class="go" id="ok">计算</button>
    </div>
  </div>
</div>

<script>
var DATA = __DATA__;
var CALC = __CALC__;
var BANDS = [[0,20,"#ef4444"],[20,40,"#f97316"],[40,60,"#94a3b8"],[60,80,"#4ade80"],[80,100,"#22c55e"]];
var W=520,H=300,L=34,R=52,T=12,B=26;
var view=[];

function bandOf(v){ for(var i=0;i<BANDS.length;i++){ var hi=BANDS[i][1]; if(v<hi||(i===BANDS.length-1&&v<=hi)) return BANDS[i]; } return BANDS[4]; }
function bandName(v){ return v<20?"顶部区":(v<40?"偏热":(v<60?"中性":(v<80?"偏冷":"谷底区"))); }
function X(i,n){ return L + i*(W-L-R)/Math.max(1,n-1); }
function Y(v){ return T + v/100*(H-T-B); }

function draw(d){
  view=d;
  var n=d.length, s='<svg viewBox="0 0 '+W+' '+H+'" class="chart">';
  BANDS.forEach(function(b){
    var y1=Y(b[0]), y2=Y(b[1]);
    s+='<rect x="'+L+'" y="'+y1+'" width="'+(W-L-R)+'" height="'+(y2-y1)+'" fill="'+b[2]+'" opacity=".08"/>';
  });
  for(var v=0;v<=100;v+=20){
    s+='<line x1="'+L+'" y1="'+Y(v)+'" x2="'+(W-R)+'" y2="'+Y(v)+'" stroke="#22304a"/>';
    s+='<text x="'+(L-6)+'" y="'+(Y(v)+3)+'" fill="#5b6b85" font-size="8" text-anchor="end">'+v+'</text>';
  }
  for(var i=1;i<n;i++){
    var c=bandOf((d[i-1][2]+d[i][2])/2)[2];
    s+='<line x1="'+X(i-1,n).toFixed(1)+'" y1="'+Y(d[i-1][2]).toFixed(1)+'" x2="'+X(i,n).toFixed(1)+
       '" y2="'+Y(d[i][2]).toFixed(1)+'" stroke="'+c+'" stroke-width="2"/>';
  }
  var step=Math.max(1,Math.floor(n/4));
  for(var j=0;j<n;j+=step){
    s+='<text x="'+X(j,n).toFixed(1)+'" y="'+(H-8)+'" fill="#5b6b85" font-size="8" text-anchor="middle">'+d[j][0].slice(5)+'</text>';
  }
  document.getElementById("chart").innerHTML=s+"</svg>";
}

function show(n){
  var sub = n ? DATA.slice(Math.max(0,DATA.length-n)) : DATA.slice();
  draw(sub);
}

document.getElementById("btns").addEventListener("click", function(e){
  var t=e.target; if(t.tagName!=="BUTTON") return;
  Array.prototype.forEach.call(this.children, function(b){ b.classList.remove("on"); });
  t.classList.add("on");
  show(parseInt(t.getAttribute("data-n"),10));
});

var wrap=document.getElementById("cwrap"), tip=document.getElementById("tip");
function pick(clientX){
  var d=view; if(!d||d.length<2) return;
  var r=wrap.getBoundingClientRect(), sx=(clientX-r.left)/r.width*W;
  if(sx<L||sx>W-R){ tip.style.display="none"; return; }
  var i=Math.max(0,Math.min(d.length-1,Math.round((sx-L)/(W-L-R)*(d.length-1))));
  tip.style.display="block";
  tip.style.left=Math.min(84,Math.max(16,X(i,d.length)/W*100))+"%";
  tip.style.top=(Y(d[i][2])/H*100)+"%";
  tip.innerHTML="<b>"+d[i][0]+"</b><br>谷底分 "+d[i][2].toFixed(0)+"<br>净值 "+d[i][1].toFixed(3);
}
wrap.addEventListener("mousemove", function(e){ pick(e.clientX); });
wrap.addEventListener("touchstart", function(e){ pick(e.touches[0].clientX); });
wrap.addEventListener("touchmove", function(e){ pick(e.touches[0].clientX); e.preventDefault(); }, {passive:false});
wrap.addEventListener("mouseleave", function(){ tip.style.display="none"; });
wrap.addEventListener("touchend", function(){ setTimeout(function(){ tip.style.display="none"; }, 1800); });

function calcScore(price){
  var P=CALC.p, S=CALC.s, R=CALC.r, n=P.length;
  var lo=0; for(var i=0;i<n;i++){ if(P[i]<=price) lo++; }
  var A = 100*(1 - lo/(n+1));
  var hi=0; for(var j=Math.max(0,n-250);j<n;j++){ if(P[j]>hi) hi=P[j]; }
  var D = 100*Math.min(1, Math.abs(price/hi-1)/0.15);
  var sp = CALC.s0 * (CALC.p0/price);
  var c=0; for(var k=0;k<n;k++){ if(S[k]<=sp) c++; }
  var E = 100*c/n;
  var raw = 0.60*D + 0.25*A + 0.15*E;
  var m=0; for(var q=0;q<n;q++){ if(R[q]<=raw) m++; }
  var score = 100*m/n;
  var ma20=0; for(var z=n-20;z<n;z++){ ma20 += P[z]; } ma20/=20;
  var gap = (ma20/price-1)*100;
  return {score:score, A:A, D:D, E:E, gap:gap, ma20:ma20};
}

function money(score, gap){
  if(score<20) return 50;
  if(score<75) return 100;
  var a=650;
  if(gap>3) a += (gap-3)*880;
  return Math.round(a);
}

var mask=document.getElementById("mask"), res=document.getElementById("result");
document.getElementById("openCalc").addEventListener("click", function(){
  mask.classList.add("on");
  document.getElementById("pxIn").focus();
});
document.getElementById("cancel").addEventListener("click", function(){ mask.classList.remove("on"); });
mask.addEventListener("click", function(e){ if(e.target===mask) mask.classList.remove("on"); });
document.getElementById("ok").addEventListener("click", function(){
  var price = parseFloat(document.getElementById("pxIn").value);
  if(!(price>0)){ return; }
  var r = calcScore(price);
  var s = r.score, b = bandOf(s), amt = money(s, r.gap);
  res.innerHTML = "<div class='big' style='color:"+b[2]+"'>"+s.toFixed(0)+" 分 · "+bandName(s)+"</div>"+
            "<div class='line'>该投 <b style='color:#38bdf8;font-size:1.05rem'>¥"+amt+"</b></div>"+
            "<div class='line'>回撤深度 "+r.D.toFixed(0)+" · 三年位置 "+r.A.toFixed(0)+" · 利差 "+r.E.toFixed(0)+"</div>"+
            "<div class='line'>MA20 约 "+r.ma20.toFixed(3)+"，偏离 "+(r.gap>0?"+":"")+r.gap.toFixed(1)+"%</div>"+
            (amt>2000 ? "<div class='line' style='color:#f59e0b'>深跌加码，金额较大，注意现金流</div>" : "");
  res.classList.add("on");
  mask.classList.remove("on");
});

show(42);
</script>
</body></html>"""

formula = "谷底分 %d → %s，投 %d 元" % (score, band_txt, int(amt - addon))
if addon:
    formula = "650 + (%.1f − 3) × 880 = %d 元" % (gap, int(amt))

html = (page.replace("__DATA__", json.dumps(series, ensure_ascii=False, separators=(",", ":")))
            .replace("__CALC__", json.dumps(calc, ensure_ascii=False, separators=(",", ":")))
            .replace("__DATE__", last["date"])
            .replace("__PRICE__", "%.3f" % last["price"])
            .replace("__EST__", "（净值未公布，按 ETF 价估算）" if frames.get("nav_estimated") else "")
            .replace("__SCORE__", "%.0f" % score)
            .replace("__BAND__", band_txt)
            .replace("__COLOR__", color)
            .replace("__PREV__", "%.0f" % prev20)
            .replace("__D__", "%.0f" % last["D"])
            .replace("__A__", "%.0f" % last["A"])
            .replace("__E__", "%.0f" % last["E"])
            .replace("__AMT__", format(int(amt), ","))
            .replace("__FORMULA__", formula))
open("mobile.html", "w", encoding="utf-8").write(html)
os.makedirs("docs", exist_ok=True)
open(os.path.join("docs", "index.html"), "w", encoding="utf-8").write(html)
print("已生成 mobile.html + docs/index.html（%.0f KB）" % (len(html) / 1024))
print("今日：谷底分 %.0f %s，投 %d 元" % (score, band_txt, amt))
