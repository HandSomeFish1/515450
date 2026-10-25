# -*- coding: utf-8 -*-
"""把 price_gap 数据画成 3 段堆叠的 PNG（便于看清数字）"""
import json

from PIL import Image, ImageDraw, ImageFont

pts = json.load(open("price_gap_pts.json", encoding="utf-8"))
n = len(pts)
hits = sum(1 for p in pts if p[2] is not None)

PANELS = 3
per = (n + PANELS - 1) // PANELS
IW, PH = 2000, 470
GAPY = 60
IH = 40 + PANELS * (PH + GAPY)
L, R, T, B = 78, 30, 46, 52

font_t = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 25)
font_s = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 15)
font_a = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 12)
font_m = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 11)

img = Image.new("RGB", (IW, IH), "#080d16")
dr = ImageDraw.Draw(img)
dr.text((L, 14), "515450 收盘曲线 · 谷底分≥75 且跌破 20 日线的日子", font=font_t, fill="#e7eef9")
dr.text((L, 44), "2023-10-09 ~ 2026-10-23 · %d 个交易日 · 触发 %d 天 · 数字＝MA20 高于收盘的百分比（%%已省略）"
        % (n, hits), font=font_s, fill="#8b9cb6")

allc = [p[1] for p in pts]
mn, mx = min(allc), max(allc)
pad = (mx - mn) * 0.10
mn -= pad
mx += pad

for k in range(PANELS):
    a, b = k * per, min(n, (k + 1) * per)
    if a >= b:
        break
    y0 = 80 + k * (PH + GAPY)

    def X(i):
        return L + (i - a) * (IW - L - R) / max(1, (b - a - 1))

    def Y(v):
        return y0 + PH - B - (v - mn) / (mx - mn) * (PH - T - B)

    for g in range(3):
        val = mn + (mx - mn) * g / 2
        yy = Y(val)
        dr.line([L, yy, IW - R, yy], fill="#1b2740")
        dr.text((L - 10, yy), "%.3f" % val, font=font_a, fill="#6b7d98", anchor="rm")

    dr.line([(X(i), Y(pts[i][1])) for i in range(a, b)], fill="#38bdf8", width=2)

    last_month = ""
    for i in range(a, b):
        d = pts[i]
        if d[0][:7] != last_month:
            last_month = d[0][:7]
            dr.line([X(i), y0 + PH - B, X(i), y0 + PH - B + 5], fill="#2a3a58")
            dr.text((X(i), y0 + PH - B + 8), last_month, font=font_a, fill="#6b7d98", anchor="ma")

    for i in range(a, b):
        d = pts[i]
        if len(d) > 3 and d[3]:
            x, yy = X(i), Y(d[1])
            dr.ellipse([x - 2.5, yy - 2.5, x + 2.5, yy + 2.5], fill="#ef4444")

    prev_x = -999
    for i in range(a, b):
        d = pts[i]
        if d[2] is None:
            continue
        x, yy = X(i), Y(d[1])
        dr.line([x, yy - 3, x, yy - 20], fill="#22c55e")
        dr.ellipse([x - 3, yy - 3, x + 3, yy + 3], fill="#22c55e")
        up = 30 if (x - prev_x < 30) else 22
        dr.text((x, yy - up - 4), "%.1f" % d[2], font=font_m, fill="#7ee2a8", anchor="mb")
        prev_x = x

img.save("price_gap.png", "PNG")
print("已生成 price_gap.png %dx%d（分 %d 段）" % (IW, IH, PANELS))
