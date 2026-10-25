# -*- coding: utf-8 -*-
"""给谷底分加平滑，验证效果并重画"""
import json
import math
import statistics as st

data = json.load(open("score_series.json", encoding="utf-8"))
dates = [x[0] for x in data]
px = [x[1] for x in data]
raw = [x[2] for x in data]
n = len(raw)


def smooth(vals, k):
    out = []
    for i in range(len(vals)):
        w = vals[max(0, i - k + 1):i + 1]
        out.append(sum(w) / len(w))
    return out


def ranks(x):
    o = sorted(range(len(x)), key=lambda i: x[i])
    r = [0] * len(x)
    for p, i in enumerate(o):
        r[i] = p + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else 0.0


for k in (1, 10, 20, 30):
    s = smooth(raw, k) if k > 1 else raw
    rho = spearman([s[i] for i in range(n - 60)], [px[i + 60] / px[i] - 1 for i in range(n - 60)])
    cross = sum(1 for i in range(1, n) if (s[i - 1] - 50) * (s[i] - 50) < 0)
    hi = [px[i + 60] / px[i] - 1 for i in range(n - 60) if s[i] > 80]
    lo = [px[i + 60] / px[i] - 1 for i in range(n - 60) if s[i] < 30]
    print("平滑 %2d 日：ρ60 %+.3f  穿50 %3d 次  >80 %+.2f%%（%d 天）  <30 %+.2f%%（%d 天）" % (
        k, rho, cross, st.mean(hi) * 100 if hi else 0, len(hi),
        st.mean(lo) * 100 if lo else 0, len(lo)))

s20 = smooth(raw, 20)
json.dump([[dates[i], px[i], round(raw[i], 1), round(s20[i], 1)] for i in range(n)],
          open("score_series_smooth.json", "w", encoding="utf-8"), ensure_ascii=False)
print("已写入 score_series_smooth.json")
