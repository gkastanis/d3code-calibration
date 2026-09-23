#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 George Kastanis
"""How many labelled examples does the calibration fix actually need?

recal.py answers "is the miscalibration a scale problem or a ranking problem"
by fitting on half the data. It does not answer "how much data", which is the
question anyone adopting the fix will ask first. This sweeps the fit-set size.

For each size n: draw n items at random as the fit set, fit the isotonic map on
them, apply it to ALL the remaining items, and score. Repeat over seeds. Every
number reported is held out of the fit.

Usage: python3 recal_curve.py ARM.jsonl [--seeds 40] [--sizes 25,50,100,150,...]
"""
from __future__ import annotations

import argparse
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import load_arm, score  # noqa: E402
from recal import pav, apply as apply_map  # noqa: E402

DEFAULT_SIZES = "25,50,100,150,250,500,1000,2000"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--arm", help="select this arm from a combined JSONL file")
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--sizes", default=DEFAULT_SIZES)
    a = ap.parse_args()

    rows = [{"p": float(r["model"]["p_offensive"]), "rate": float(r["human"]["rate"])}
            for r in load_arm(a.file, a.arm) if r["human"].get("rate") is not None]
    print(f"{a.file.name}: n={len(rows)}, {a.seeds} seeds per size")

    raw = score([r["p"] for r in rows], [r["rate"] for r in rows])
    base_p = statistics.fmean(r["rate"] for r in rows)
    base = score([base_p] * len(rows), [r["rate"] for r in rows])
    print(f"  raw (no fit)      brier={raw['brier']:.4f} ece={raw['ece']:.4f}")
    print(f"  constant base rate brier={base['brier']:.4f}")
    print()
    print(f"{'fit items':>10} {'brier':>8} {'ece':>8} {'vs raw':>9} {'vs base':>9}")

    sizes = [int(s) for s in a.sizes.split(",") if int(s) < len(rows)]
    for n in sizes:
        briers, eces = [], []
        for seed in range(a.seeds):
            rng = random.Random(seed * 7919 + n)
            idx = list(range(len(rows)))
            rng.shuffle(idx)
            fit = [rows[i] for i in idx[:n]]
            held = [rows[i] for i in idx[n:]]
            knots = pav([r["p"] for r in fit], [r["rate"] for r in fit])
            ps = [apply_map(knots, r["p"]) for r in held]
            s = score(ps, [r["rate"] for r in held])
            briers.append(s["brier"])
            eces.append(s["ece"])
        b, e = statistics.fmean(briers), statistics.fmean(eces)
        print(f"{n:>10} {b:>8.4f} {e:>8.4f} "
              f"{(1 - b / raw['brier']) * 100:>8.0f}% {(1 - b / base['brier']) * 100:>8.0f}%")
    print("\n'vs raw' and 'vs base' are percent reduction in Brier, held out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
