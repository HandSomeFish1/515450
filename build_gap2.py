# -*- coding: utf-8 -*-
"""谷底分 >= 75 且 MA20 > 收盘价：偏离幅度分布"""
import collections
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

t3 = [r for r in trough.build(frames) if r["date"] >= "2023-10-01" and r["score"] >= 75]
gaps = [(ma20[r["date"]] / r["price"] - 1) * 100 for r in t3 if r["date"] in ma20]
pos = [g for g in gaps if g > 0]

bins_n = int(max(pos) // 0.5) + 1
counts = [0] * bins_n
for g in pos:
    counts[min(bins_n - 1, int(g // 0.5))] += 1
n = len(pos)
mx = max(pos)
mean = sum(pos) / n
ge3 = sum(1 for g in pos if g >= 3)
ge1 = sum(1 for g in pos if g >= 1)

W, H = 1400, 720
L, R, T, B = 80, 40, 92, 620
img = Image.new("RGB", (W, H), "#080d16")
dr = ImageDraw.Draw(img)
f_title = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 26)
f_sub = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
f_axis = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
f_val = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)

dr.text((L, 22), "谷底分 ≥ 75 且 MA20 高于收盘价：偏离幅度分布", font=f_title, fill="#e7eef9")
dr.text((L, 58), "2023-10-09 ~ 2026-10-23 · 满足条件 %d 天 · 每 0.5%% 一档 · 均值 %+.2f%% · 最大 %+.2f%%"
        % (n, mean, mx), font=f_sub, fill="#8b9cb6")

top = ((max(counts) // 5) + 1) * 5
bw = (W - L - R) / float(bins_n)


def y(v):
    return B - v / float(top) * (B - T)


for g in range(0, top + 1, 5):
    dr.line([L, y(g), W - R, y(g)], fill="#1b2740")
    dr.text((L - 12, y(g)), str(g), font=f_axis, fill="#6b7d98", anchor="rm")

for i, c in enumerate(counts):
    x0 = L + i * bw + 4
    x1 = L + (i + 1) * bw - 4
    lo = i * 0.5
    color = "#22c55e" if lo >= 3 else "#38bdf8"     # 3% 以上＝加码区
    dr.rectangle([x0, y(c), x1, B], fill=color)
    if c:
        dr.text(((x0 + x1) / 2, y(c) - 12), str(c), font=f_val, fill="#cfe0f5", anchor="ma")

for i in range(bins_n):
    dr.text((L + (i + 0.5) * bw, B + 10), "%.1f" % (i * 0.5), font=f_axis, fill="#8b9cb6", anchor="ma")

dr.line([L, B, W - R, B], fill="#2a3a58")
dr.text(((L + W - R) / 2, B + 44), "MA20 比收盘价高的百分比（%）",
        font=f_axis, fill="#6b7d98", anchor="ma")

# 3% 门槛线
x3 = L + (3.0 / 0.5) * bw
dr.line([x3, T - 8, x3, B], fill="#f59e0b", width=2)
dr.text((x3 + 8, T + 2), "3% 加码门槛", font=f_axis, fill="#f59e0b")

dr.text((L, H - 42), "≥3%% 共 %d 天（占 %.0f%%）    ≥1%% 共 %d 天（占 %.0f%%）"
        % (ge3, 100.0 * ge3 / n, ge1, 100.0 * ge1 / n), font=f_sub, fill="#8b9cb6")

img.save("gap_hist2.png", "PNG")
print("满足条件 %d 天（谷底分≥75 共 %d 天，其中 %.0f%% 跌破均线）" % (n, len(gaps), 100.0 * n / len(gaps)))
print("≥3%%: %d 天, ≥1%%: %d 天, 最大 %.2f%%, 均值 %.2f%%" % (ge3, ge1, mx, mean))
print("已生成 gap_hist2.png")
