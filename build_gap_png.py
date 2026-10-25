# -*- coding: utf-8 -*-
"""把 MA20 偏离分布画成 PNG"""
import json

from PIL import Image, ImageDraw, ImageFont

d = json.load(open("gap_hist.json", encoding="utf-8"))
bins = d["bins"]
n, mean, median, pos, mx = d["n"], d["mean"], d["median"], d["pos"], d["max"]
counts = [b[1] for b in bins]
top = max(counts)
ymax = ((top // 10) + 1) * 10

W, H = 1400, 720
L, R, T, B = 80, 40, 90, 620
img = Image.new("RGB", (W, H), "#080d16")
dr = ImageDraw.Draw(img)
f_title = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 26)
f_sub = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
f_axis = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
f_val = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 13)

dr.text((L, 22), "MA20 高于收盘价的幅度分布", font=f_title, fill="#e7eef9")
dr.text((L, 58), "2023-10-09 ~ 2026-10-23 · 谷底分 ≤ 75 · 每 0.5%% 一档 · 共 %d 天" % n,
        font=f_sub, fill="#8b9cb6")

bw = (W - L - R) / float(len(bins))
gap = 3


def y(v):
    return B - v / float(ymax) * (B - T)


for g in range(0, ymax + 1, 10):
    dr.line([L, y(g), W - R, y(g)], fill="#1b2740")
    dr.text((L - 12, y(g) - 8), str(g), font=f_axis, fill="#6b7d98", anchor="ra")

for i, (val, c) in enumerate(bins):
    x0 = L + i * bw + gap / 2
    x1 = L + (i + 1) * bw - gap / 2
    color = "#4ade80" if val < 0 else "#f97316"
    dr.rectangle([x0, y(c), x1, B], fill=color)
    if c >= 10:
        dr.text(((x0 + x1) / 2, y(c) - 14), str(c), font=f_val, fill="#cfe0f5", anchor="ma")

for i, (val, c) in enumerate(bins):
    if i % 4 == 0:
        dr.text((L + (i + 0.5) * bw, B + 10), ("+" if val > 0 else "") + "%.1f%%" % val,
                font=f_axis, fill="#8b9cb6", anchor="ma")

dr.line([L, B, W - R, B], fill="#2a3a58")
dr.text(((L + W - R) / 2, B + 40), "MA20 比收盘价高的百分比（左边＝收盘高于均线，右边＝价格在均线下方）",
        font=f_axis, fill="#6b7d98", anchor="ma")

stats = "均值 %+.2f%%    中位数 %+.2f%%    MA20 高于收盘 %d%%    最大 %+.2f%%" % (
    mean, median, 100.0 * pos / n, mx)
dr.text((L, H - 40), stats, font=f_sub, fill="#8b9cb6")

img.save("gap_hist.png", "PNG")
print("已生成 gap_hist.png %dx%d" % (W, H))
