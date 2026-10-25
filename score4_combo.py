# -*- coding: utf-8 -*-
"""组合测试：便宜（利差）+ 企稳（RSI/动量）能不能两段都为正"""
import math
import statistics as st

exec(open("score4_try.py", encoding="utf-8").read().split('print("样本')[0])


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


i21 = next(i for i, f in enumerate(feat) if f["d"] >= "2021-02")
i23 = next(i for i, f in enumerate(feat) if f["d"] >= "2023-01")
end = len(feat) - 61

COMBOS = {
    "利差 50 + RSI 50": lambda f: 0.5 * f["sp_pct"] + 0.5 * f["r_pct"],
    "利差 60 + RSI 40": lambda f: 0.6 * f["sp_pct"] + 0.4 * f["r_pct"],
    "利差 40 + RSI 30 + 斜率 30": lambda f: 0.4 * f["sp_pct"] + 0.3 * f["r_pct"] + 0.3 * (100 if f["turn"] else 0),
    "利差 50 + 距20线 50": lambda f: 0.5 * f["sp_pct"] + 0.5 * (100 - f["d20_pct"] * 100),
    "纯利差": lambda f: f["sp_pct"],
    "纯 RSI": lambda f: f["r_pct"],
}

print("%-26s %s" % ("组合", "全样本 / 2021-22 / 2023-26（ρ、最高档后60日均值、最低档）"))
for name, fn in COMBOS.items():
    sc = [fn(f) for f in feat]
    out = []
    for label, a, b in (("全", i21, end), ("21-22", i21, min(i23, end)), ("23-26", i23, end)):
        if b - a < 120:
            out.append("%s n/a" % label)
            continue
        idx = list(range(a, b))
        rho = spearman([sc[i] for i in idx], [feat[i + 60]["p"] / feat[i]["p"] - 1 for i in idx])
        s = sorted(sc[i] for i in idx)
        hi_thr = s[int(len(s) * 0.8)]
        lo_thr = s[int(len(s) * 0.2)]
        hi = [feat[i + 60]["p"] / feat[i]["p"] - 1 for i in idx if sc[i] >= hi_thr]
        lo = [feat[i + 60]["p"] / feat[i]["p"] - 1 for i in idx if sc[i] <= lo_thr]
        out.append("%s ρ%+.2f 高%+.1f%% 低%+.1f%%" % (label, rho, st.mean(hi) * 100, st.mean(lo) * 100))
    print("%-26s %s" % (name, " | ".join(out)))
