# -*- coding: utf-8 -*-
"""最终版：20 日平滑的谷底分 → JSON（给页面用）+ PNG"""
import json

from PIL import Image, ImageDraw, ImageFont

data = json.load(open("score_series_smooth.json", encoding="utf-8"))
dates = [x[0] for x in data]
px = [x[1] for x in data]
raw = [x[2] for x in data]
sm = [x[3] for x in data]
n = len(data)

# 给页面用：平滑后的分数
json.dump([[dates[i], px[i], round(sm[i], 1)] for i in range(n)],
          open("score_series.json", "w", encoding="utf-8"), ensure_ascii=False)

BANDS = [(0, 20, "#ef4444", "顶部区"), (20, 40, "#f97316", "偏热"),
         (40, 60, "#94a3b8", "中性"), (60, 80, "#4ade80", "偏冷"),
         (80, 100, "#22c55e", "谷底区")]
W, H = 1500, 660
L, R, T, B = 74, 1250, 40, 600
img = Image.new("RGB", (W, H), "#080d16")
ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
do = ImageDraw.Draw(ov)
font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
fs = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 15)


def X(i):
    return L + i * (R - L) / (n - 1)


def Y(v):
    return T + v / 100.0 * (B - T)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


for a, b, c, name in BANDS:
    do.rectangle([L, Y(a), R, Y(b)], fill=rgb(c) + (16,))
    d.text((R + 8, Y((a + b) / 2) - 9), "%d–%d %s" % (a, b, name), font=fs, fill=c)
for v in range(0, 101, 20):
    d.line([L, Y(v), R, Y(v)], fill="#22304a")
    d.text((L - 40, Y(v) - 9), str(v), font=fs, fill="#6b7d98")

# 细线：原始分
d.line([(X(i), Y(raw[i])) for i in range(n)], fill="#2b4364", width=1)
# 粗线：20 日平滑
for i in range(1, n):
    mid = (sm[i - 1] + sm[i]) / 2
    c = next(b[2] for b in BANDS if mid < b[1] or b[1] == 100)
    d.line([X(i - 1), Y(sm[i - 1]), X(i), Y(sm[i])], fill=c, width=4)

step = max(1, n // 10)
for i in range(0, n, step):
    d.text((X(i) - 22, B + 12), dates[i][:7], font=fs, fill="#6b7d98")

img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
d = ImageDraw.Draw(img)
d.text((L, 8), "515450 谷底分（20 日平滑） · %s ~ %s" % (dates[0], dates[-1]), font=font, fill="#e7eef9")
d.text((L + 560, 10), "当前 %.0f 分" % sm[-1], font=font, fill="#7dd3fc")
d.text((L, B + 38), "粗线＝20 日平滑，细线＝原始分；纵轴翻转：0 在上、100 在下", font=fs, fill="#5b6b85")
img.save("score3_curve.png", "PNG")
print("已生成 score3_curve.png，并更新 score_series.json（%d 天，平滑后）" % n)
