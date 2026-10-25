# -*- coding: utf-8 -*-
"""把谷底分曲线渲染成 PNG"""
import json

from PIL import Image, ImageDraw, ImageFont

data = json.load(open("score_series.json", encoding="utf-8"))
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
fb = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 15)

n = len(data)
dates = [x[0] for x in data]
scores = [x[2] for x in data]


def X(i):
    return L + i * (R - L) / (n - 1)


def Y(v):
    return T + v / 100.0 * (B - T)


def hex2rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


for a, b, c, name in BANDS:
    col = hex2rgb(c)
    do.rectangle([L, Y(a), R, Y(b)], fill=col + (18,))
    d.text((R + 8, Y((a + b) / 2) - 9), "%d–%d %s" % (a, b, name), font=fs, fill=c)

for v in range(0, 101, 20):
    d.line([L, Y(v), R, Y(v)], fill="#22304a")
    d.text((L - 40, Y(v) - 9), str(v), font=fs, fill="#6b7d98")

for i in range(1, n):
    mid = (scores[i - 1] + scores[i]) / 2
    c = next(b[2] for b in BANDS if mid < b[1] or b[1] == 100)
    d.line([X(i - 1), Y(scores[i - 1]), X(i), Y(scores[i])], fill=c, width=3)

step = max(1, n // 10)
for i in range(0, n, step):
    d.text((X(i) - 22, B + 12), dates[i][:7], font=fs, fill="#6b7d98")

img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
d = ImageDraw.Draw(img)
d.text((L, 8), "515450 谷底分 · %s ~ %s" % (dates[0], dates[-1]), font=font, fill="#e7eef9")
d.text((L + 420, 10), "当前 %.0f 分" % scores[-1], font=fb, fill="#7dd3fc")
d.text((L, B + 38), "分数越高越接近谷底（纵轴已翻转：0 在上，100 在下）", font=fs, fill="#5b6b85")

img.save("score3_curve.png", "PNG")
print("已生成 score3_curve.png  %dx%d" % img.size)
