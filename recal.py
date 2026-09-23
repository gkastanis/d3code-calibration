#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 George Kastanis
"""Split-half recalibration: is an arm's miscalibration a scale problem or a ranking problem?

Fit a monotone (isotonic, pool-adjacent-violators) map from model p to human
rate on half the items, apply it to the other half, and score. Repeat with the
halves swapped and over several seeds; report mean Brier and ECE before and
after. If recalibrated Brier beats the base rate, the model carries real
signal and only its scale is off. If not, the ranking itself is weak.

Usage: python3 recal.py ARM.jsonl [--seeds 20]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import load_arm, score  # noqa: E402
import explain  # noqa: E402


def pav(xs: list[float], ys: list[float]) -> list[tuple[float, float]]:
    """Isotonic regression by pool-adjacent-violators; returns (x, fitted) knots sorted by x."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    blocks = [[xs[i], ys[i], 1.0] for i in order]  # x, mean y, weight
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][1] > blocks[i + 1][1]:
            a, b = blocks[i], blocks[i + 1]
            w = a[2] + b[2]
            merged = [b[0], (a[1] * a[2] + b[1] * b[2]) / w, w]
            blocks[i:i + 2] = [merged]
            i = max(i - 1, 0)
        else:
            i += 1
    return [(b[0], b[1]) for b in blocks]


def apply(knots: list[tuple[float, float]], x: float) -> float:
    prev = knots[0][1]
    for kx, ky in knots:
        if x <= kx:
            return ky
        prev = ky
    return prev


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--arm", help="select this arm from a combined JSONL file")
    ap.add_argument("--seeds", type=int, default=20)
    a = ap.parse_args()
    rows = load_arm(a.file, a.arm)
    p = [float(r["model"]["p_offensive"]) for r in rows]
    y = [float(r["human"]["rate"]) for r in rows]
    n = len(rows)
    before = score(p, y)
    base = sum(y) / n
    base_s = score([base] * n, y)
    briers, eces, aucs = [], [], []
    for seed in range(a.seeds):
        idx = list(range(n))
        random.Random(seed).shuffle(idx)
        half = n // 2
        for train, test in ((idx[:half], idx[half:]), (idx[half:], idx[:half])):
            knots = pav([p[i] for i in train], [y[i] for i in train])
            pt = [apply(knots, p[i]) for i in test]
            s = score(pt, [y[i] for i in test])
            briers.append(s["brier"]); eces.append(s["ece"])
            if s["auc"] is not None:
                aucs.append(s["auc"])
    m = lambda xs: sum(xs) / len(xs)
    print(f"{a.file.name}: n={n}")
    print(f"  before recal : brier={before['brier']:.3f} ece={before['ece']:.3f} auc={before['auc']:.3f}")
    print(f"  after  recal : brier={m(briers):.3f} ece={m(eces):.3f} auc={m(aucs):.3f}   (split-half isotonic, {a.seeds} seeds x 2 folds, held-out)")
    print(f"  base rate    : brier={base_s['brier']:.3f} ece={base_s['ece']:.3f} (constant p={base:.3f})")
    for line in explain.explain_recal(before, m(briers), m(eces), m(aucs), base_s['brier']):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
