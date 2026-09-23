#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 George Kastanis
"""Bootstrap confidence intervals, and paired tests for the between-arm gaps.

Every other table in this study reports point estimates. A reader comparing
0.858 against 0.798 is entitled to ask whether that gap is real, and until this
script existed the answer was "nobody checked".

Resamples items with replacement (`--boots`, default 1000) and reports the 2.5th
and 97.5th percentiles of each metric. For two arms it also reports a PAIRED
bootstrap of the difference: the same resampled item ids are scored under both
arms, which is the right test here because both arms answered the same items, so
the comparison is not weakened by item difficulty varying between resamples. The
difference is significant at the 5% level when the interval excludes zero.

Usage:
    python3 intervals.py results-compact.jsonl --arm jev-full
    python3 intervals.py results-compact.jsonl --arm jev-full --vs laya-full
    python3 intervals.py results-compact.jsonl --arm jev-100 --vs sonnet-100 --boots 2000
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import load_arm, score  # noqa: E402

METRICS = ("brier", "ece", "spearman", "auc", "acc@0.5")


def pairs(path: Path, arm: str) -> dict[str, tuple[float, float]]:
    """item_id -> (model p, human rate) for one arm."""
    out = {}
    for r in load_arm(path, arm):
        rate = r["human"].get("rate")
        if rate is not None:
            out[r["item_id"]] = (float(r["model"]["p_offensive"]), float(rate))
    return out


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    i = q * (len(xs) - 1)
    lo, hi = int(i), min(int(i) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def boot(ids: list[str], data: dict, boots: int, seed: int) -> dict[str, list[float]]:
    rng = random.Random(seed)
    n = len(ids)
    out: dict[str, list[float]] = {m: [] for m in METRICS}
    for _ in range(boots):
        pick = [ids[rng.randrange(n)] for _ in range(n)]
        s = score([data[i][0] for i in pick], [data[i][1] for i in pick])
        for m in METRICS:
            if s[m] is not None:
                out[m].append(s[m])
    return out


def boot_diff(ids: list[str], a: dict, b: dict, boots: int, seed: int) -> dict[str, list[float]]:
    """Paired: one resample of item ids, scored under both arms, difference taken."""
    rng = random.Random(seed)
    n = len(ids)
    out: dict[str, list[float]] = {m: [] for m in METRICS}
    for _ in range(boots):
        pick = [ids[rng.randrange(n)] for _ in range(n)]
        sa = score([a[i][0] for i in pick], [a[i][1] for i in pick])
        sb = score([b[i][0] for i in pick], [b[i][1] for i in pick])
        for m in METRICS:
            if sa[m] is not None and sb[m] is not None:
                out[m].append(sa[m] - sb[m])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", type=Path)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--vs", help="second arm; adds a paired bootstrap of the difference")
    ap.add_argument("--boots", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    A = pairs(a.results, a.arm)
    if not A:
        sys.exit(f"no usable rows for arm {a.arm!r}")

    if a.vs:
        B = pairs(a.results, a.vs)
        ids = sorted(set(A) & set(B))
        if not ids:
            sys.exit(f"arms {a.arm!r} and {a.vs!r} share no item ids")
        print(f"{a.arm} vs {a.vs}: {len(ids)} shared items, "
              f"{a.boots} bootstrap resamples, 95% intervals\n")
    else:
        ids = sorted(A)
        print(f"{a.arm}: n={len(ids)}, {a.boots} bootstrap resamples, 95% intervals\n")

    pa = score([A[i][0] for i in ids], [A[i][1] for i in ids])
    da = boot(ids, A, a.boots, a.seed)
    if not a.vs:
        print(f"{'metric':<10} {'point':>8} {'95% CI':>20}")
        for m in METRICS:
            if pa[m] is None or not da[m]:
                continue
            print(f"{m:<10} {pa[m]:>8.4f}   [{pct(da[m], .025):.4f}, {pct(da[m], .975):.4f}]")
        return 0

    pb = score([B[i][0] for i in ids], [B[i][1] for i in ids])
    db = boot(ids, B, a.boots, a.seed)
    dd = boot_diff(ids, A, B, a.boots, a.seed + 1)

    print(f"{'metric':<10} {a.arm[:14]:>16} {a.vs[:14]:>16}   "
          f"{'difference (paired)':>26}  significant")
    for m in METRICS:
        if pa[m] is None or pb[m] is None or not dd[m]:
            continue
        lo, hi = pct(dd[m], .025), pct(dd[m], .975)
        sig = "yes" if (lo > 0 or hi < 0) else "no"
        print(f"{m:<10} {pa[m]:>7.4f} [{pct(da[m], .025):.3f},{pct(da[m], .975):.3f}] "
              f"{pb[m]:>7.4f} [{pct(db[m], .025):.3f},{pct(db[m], .975):.3f}]   "
              f"{pa[m] - pb[m]:>+8.4f} [{lo:+.4f},{hi:+.4f}]  {sig}")
    print("\n'significant' means the paired 95% interval for the difference excludes zero.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
