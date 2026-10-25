# -*- coding: utf-8 -*-
"""谷底分单页：预设区间 + 自定义起止日期 + 鼠标悬停提示"""
import json

data = json.load(open("score_series.json", encoding="utf-8"))
series = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

page = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>515450 谷底分（利差分位） · 可调区间</title>
<style>
 body{margin:0;padding:24px 16px;background:#080d16;color:#e7eef9;
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,sans-serif;
      font-variant-numeric:tabular-nums}
 .wrap{max-width:960px;margin:0 auto}
 h1{font-size:1.3rem;margin:0 0 4px}
 .sub{color:#8b9cb6;font-size:.8rem;margin-bottom:16px}
 .card{background:linear-gradient(180deg,rgba(255,255,255,.03),rgba(255,255,255,0)) #111a2b;
       border:1px solid #22304a;border-radius:16px;padding:18px;margin-bottom:14px}
 .top{display:flex;align-items:flex-end;justify-content:space-between;gap:14px;flex-wrap:wrap}
 .score{font-size:3rem;font-weight:800;line-height:1}
 .pill{display:inline-block;margin-left:12px;padding:4px 14px;border-radius:999px;
       font-size:.85rem;vertical-align:middle}
 .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-top:14px}
 .m{background:#0d1522;border:1px solid #22304a;border-radius:10px;padding:9px 13px}
 .m .k{font-size:.68rem;color:#8b9cb6}
 .m .v{font-size:1rem;font-weight:650;margin-top:2px}
 .controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
 .controls label{font-size:.76rem;color:#8b9cb6;display:flex;align-items:center;gap:6px}
 .controls input[type=date]{background:#0d1522;border:1px solid #2a3a58;color:#e7eef9;
       border-radius:8px;padding:5px 8px;font-size:.78rem;color-scheme:dark}
 .btns{display:flex;gap:8px;flex-wrap:wrap}
 button{background:#0d1522;border:1px solid #2a3a58;color:#b8cbe4;border-radius:999px;
        padding:6px 15px;font-size:.78rem;cursor:pointer}
 button.on{background:#1d4ed8;border-color:#3b82f6;color:#fff}
 button:hover{border-color:#3b82f6}
 .chartwrap{position:relative}
 .chart{width:100%;height:auto;display:block}
 .vline{position:absolute;top:0;bottom:0;width:1px;background:#38bdf8;opacity:.55;
        display:none;pointer-events:none}
 .dot{position:absolute;width:9px;height:9px;border-radius:50%;border:2px solid #080d16;
      transform:translate(-50%,-50%);display:none;pointer-events:none;box-shadow:0 0 0 1px rgba(255,255,255,.5)}
 .tip{position:absolute;display:none;pointer-events:none;background:#0b1424;border:1px solid #38bdf8;
      border-radius:8px;padding:6px 10px;font-size:.76rem;line-height:1.5;color:#e7eef9;
      transform:translate(-50%,-115%);white-space:nowrap;box-shadow:0 8px 20px rgba(0,0,0,.5);z-index:5}
 .tip b{color:#7dd3fc}
 .note{color:#8b9cb6;font-size:.74rem;line-height:1.7;margin-top:10px}
 .legend{display:flex;gap:14px;flex-wrap:wrap;font-size:.74rem;color:#8b9cb6;margin-bottom:8px}
 .legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}
</style></head><body><div class="wrap">
<h1>515450 谷底分 · 可调区间</h1>
<div class="sub">分数越高越接近可买区域 · 鼠标移到曲线上可看当天具体分数（纵向已翻转：越往下分数越高）</div>

<div class="card">
  <div class="top">
    <div><span class="score" id="cur">--</span><span class="pill" id="pill"></span></div>
    <div class="note" id="range" style="margin:0"></div>
  </div>
  <div class="metrics" id="metrics"></div>
</div>

<div class="card">
  <div class="controls">
    <label>起 <input type="date" id="start"></label>
    <label>止 <input type="date" id="end"></label>
    <button id="apply">应用</button>
    <span class="btns" id="btns">
      <button data-n="21">近 1 月</button>
      <button data-n="42" class="on">近 2 月</button>
      <button data-n="63">近 3 月</button>
      <button data-n="126">近半年</button>
      <button data-n="250">近 1 年</button>
      <button data-n="0">全部</button>
    </span>
  </div>
  <div class="legend" id="legend"></div>
  <div class="chartwrap" id="wrap">
    <div id="chart"></div>
    <div class="vline" id="vline"></div>
    <div class="dot" id="dot"></div>
    <div class="tip" id="tip"></div>
  </div>
  <div class="note">线色 = 分数所在区间。分数 = 便宜度在近 750 个交易日中的分位，
    便宜度 = 0.60×回撤深度 + 0.25×三年位置 + 0.15×利差位置。</div>
</div>

<div class="card">
  <div class="note" style="margin:0 0 6px">对应净值：</div>
  <div id="price"></div>
</div>
</div>

<script>
var DATA = __SERIES__;
var BANDS = [[0,20,"#ef4444","顶部区"],[20,40,"#f97316","偏热"],[40,60,"#94a3b8","中性"],
             [60,80,"#4ade80","偏冷"],[80,100,"#22c55e","谷底区"]];
var W=900, H=320, L=44, R=104, T=14, B=30;
var view = [];

function bandOf(v){ for (var i=0;i<BANDS.length;i++){ var hi=BANDS[i][1]; if (v<hi || (i===BANDS.length-1 && v<=hi)) return BANDS[i]; } return BANDS[4]; }

document.getElementById("legend").innerHTML = BANDS.map(function(b){
  return '<span><i style="background:'+b[2]+'"></i>'+b[0]+'–'+b[1]+' '+b[3]+'</span>';
}).join("");

var startEl = document.getElementById("start");
var endEl = document.getElementById("end");
startEl.min = endEl.min = DATA[0][0];
startEl.max = endEl.max = DATA[DATA.length-1][0];
startEl.value = DATA[0][0];
endEl.value = DATA[DATA.length-1][0];

function X(i,n){ return L + i*(W-L-R)/Math.max(1,n-1); }
function Y(v){ return T + v/100*(H-T-B); }

function scoreSvg(d){
  var n=d.length, s='<svg viewBox="0 0 '+W+' '+H+'" class="chart" id="svgScore">';
  BANDS.forEach(function(b){
    var y1=Y(b[0]), y2=Y(b[1]);
    s+='<rect x="'+L+'" y="'+y1+'" width="'+(W-L-R)+'" height="'+(y2-y1)+'" fill="'+b[2]+'" opacity=".07"/>';
    s+='<text x="'+(W-R+6)+'" y="'+((y1+y2)/2+3)+'" fill="'+b[2]+'" font-size="10">'+b[0]+'–'+b[1]+' '+b[3]+'</text>';
  });
  for(var v=0;v<=100;v+=20){
    s+='<line x1="'+L+'" y1="'+Y(v)+'" x2="'+(W-R)+'" y2="'+Y(v)+'" stroke="#22304a"/>';
    s+='<text x="'+(L-8)+'" y="'+(Y(v)+3)+'" fill="#6b7d98" font-size="10" text-anchor="end">'+v+'</text>';
  }
  for(var i=1;i<n;i++){
    var c=bandOf((d[i-1][2]+d[i][2])/2)[2];
    s+='<line x1="'+X(i-1,n).toFixed(1)+'" y1="'+Y(d[i-1][2]).toFixed(1)+'" x2="'+X(i,n).toFixed(1)+
       '" y2="'+Y(d[i][2]).toFixed(1)+'" stroke="'+c+'" stroke-width="2"/>';
  }
  var step=Math.max(1,Math.floor(n/8));
  for(var j=0;j<n;j+=step){
    s+='<text x="'+X(j,n).toFixed(1)+'" y="'+(H-8)+'" fill="#6b7d98" font-size="10" text-anchor="middle">'+d[j][0].slice(5)+'</text>';
  }
  return s+"</svg>";
}

function priceSvg(d){
  var n=d.length, PH=130, pl=44, pr=14, pt=8, pb=22;
  var ps=d.map(function(x){return x[1];}), mn=Math.min.apply(null,ps), mx=Math.max.apply(null,ps);
  function PX(i){ return pl + i*(W-pl-pr)/Math.max(1,n-1); }
  function PY(v){ return PH-pb - (v-mn)/Math.max(1e-6,mx-mn)*(PH-pt-pb); }
  var s='<svg viewBox="0 0 '+W+' '+PH+'" class="chart">';
  s+='<polyline fill="none" stroke="#38bdf8" stroke-width="1.6" points="'+
     d.map(function(x,i){return PX(i).toFixed(1)+","+PY(x[1]).toFixed(1);}).join(" ")+'"/>';
  var step=Math.max(1,Math.floor(n/8));
  for(var j=0;j<n;j+=step){
    s+='<text x="'+PX(j).toFixed(1)+'" y="'+(PH-6)+'" fill="#6b7d98" font-size="10" text-anchor="middle">'+d[j][0].slice(5)+'</text>';
  }
  return s+"</svg>";
}

function render(d){
  view = d;
  var last=d[d.length-1], b=bandOf(last[2]);
  var cur=document.getElementById("cur");
  cur.textContent=last[2].toFixed(0); cur.style.color=b[2];
  var pill=document.getElementById("pill");
  pill.textContent=b[3]; pill.style.color=b[2]; pill.style.border="1px solid "+b[2];
  document.getElementById("range").textContent=d[0][0]+" ~ "+last[0]+" · "+d.length+" 个交易日";
  var vals=d.map(function(x){return x[2];});
  var mean=vals.reduce(function(a,c){return a+c;},0)/vals.length;
  document.getElementById("metrics").innerHTML=
    '<div class="m"><div class="k">区间均值</div><div class="v">'+mean.toFixed(0)+'</div></div>'+
    '<div class="m"><div class="k">区间最高</div><div class="v">'+Math.max.apply(null,vals).toFixed(0)+'</div></div>'+
    '<div class="m"><div class="k">区间最低</div><div class="v">'+Math.min.apply(null,vals).toFixed(0)+'</div></div>'+
    '<div class="m"><div class="k">>80 天数</div><div class="v">'+vals.filter(function(v){return v>80;}).length+' 天</div></div>'+
    '<div class="m"><div class="k">最新净值</div><div class="v">'+last[1].toFixed(3)+'</div></div>';
  document.getElementById("chart").innerHTML=scoreSvg(d);
  document.getElementById("price").innerHTML=priceSvg(d);
}

function applyRange(){
  var a=startEl.value, z=endEl.value;
  if(!a || !z || a>z) return;
  var d=DATA.filter(function(x){ return x[0]>=a && x[0]<=z; });
  if(d.length<2){ alert("区间太短，至少选两个交易日"); return; }
  render(d);
}

document.getElementById("btns").addEventListener("click", function(e){
  var t=e.target;
  if(t.tagName!=="BUTTON") return;
  Array.prototype.forEach.call(this.children, function(b){ b.classList.remove("on"); });
  t.classList.add("on");
  var n=parseInt(t.getAttribute("data-n"),10);
  var sub = n ? DATA.slice(Math.max(0, DATA.length-n)) : DATA.slice();
  startEl.value=sub[0][0];
  endEl.value=sub[sub.length-1][0];
  render(sub);
});

document.getElementById("apply").addEventListener("click", applyRange);
startEl.addEventListener("change", applyRange);
endEl.addEventListener("change", applyRange);

// ---- 悬停 ----
var wrap=document.getElementById("wrap");
var vline=document.getElementById("vline");
var dot=document.getElementById("dot");
var tip=document.getElementById("tip");

wrap.addEventListener("mousemove", function(e){
  var d=view; if(!d || d.length<2) return;
  var r=wrap.getBoundingClientRect();
  var svgX=(e.clientX-r.left)/r.width*W;
  if(svgX<L || svgX>W-R){ hide(); return; }
  var i=Math.round((svgX-L)/(W-L-R)*(d.length-1));
  i=Math.max(0,Math.min(d.length-1,i));
  var px=X(i,d.length)/W*100, py=Y(d[i][2])/H*100;
  var b=bandOf(d[i][2]);
  vline.style.display="block"; vline.style.left=px+"%";
  dot.style.display="block"; dot.style.left=px+"%"; dot.style.top=py+"%";
  dot.style.background=b[2];
  tip.style.display="block";
  tip.style.left=Math.min(88,Math.max(12,px))+"%";
  tip.style.top=py+"%";
  tip.innerHTML="<b>"+d[i][0]+"</b><br>谷底分 "+d[i][2].toFixed(0)+" · "+b[3]+
                "<br>净值 "+d[i][1].toFixed(3);
});
wrap.addEventListener("mouseleave", hide);
function hide(){ vline.style.display="none"; dot.style.display="none"; tip.style.display="none"; }

render(DATA.slice(-42));
</script>
</body></html>"""

html = page.replace("__SERIES__", series)
open("score3_live.html", "w", encoding="utf-8").write(html)
print("已生成 score3_live.html（%d 个交易日，含日期筛选与悬停提示）" % len(data))
