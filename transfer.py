#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 George Kastanis
"""Transfer: does a correction fitted on one set of answers fix another set?

recal.py fits a correction on half the items and tests it on the other half of
the same arm. Real sites want to reuse a correction: on new kinds of content,
or on another model. This script fits the same isotonic map as recal.py and
tests it where it was not fitted:

  same      fit on half the items, test on the other half (the recal.py case)
  category  fit on every category but one, test on the one left out
  model     fit on one arm's answers for half the items, test on another arm's
            answers for the other half, next to that arm's own correction

Usage: python3 transfer.py results-compact.jsonl [--arm jev-full]
       [--other laya-full] [--seeds 20]
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import load_arm, score  # noqa: E402
from recal import apply, pav  # noqa: E402


def pairs(rows: list[dict]) -> dict[str, tuple[float, float]]:
    return {r["item_id"]: (float(r["model"]["p_offensive"]), float(r["human"]["rate"])) for r in rows}


def fit_test(fit: list[tuple[float, float]], test: list[tuple[float, float]]) -> tuple[float, float]:
    """Held-out ECE before and after a correction fitted on `fit`."""
    knots = pav([p for p, _ in fit], [y for _, y in fit])
    p = [p for p, _ in test]
    y = [y for _, y in test]
    return score(p, y)["ece"], score([apply(knots, x) for x in p], y)["ece"]


def halves(ids: list[str], seeds: int):
    for seed in range(seeds):
        idx = list(ids)
        random.Random(seed).shuffle(idx)
        half = len(idx) // 2
        yield idx[:half], idx[half:]
        yield idx[half:], idx[:half]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--arm", default="jev-full")
    ap.add_argument("--other", default="laya-full", help="the arm to move the correction to")
    ap.add_argument("--seeds", type=int, default=20)
    a = ap.parse_args()
    rows = load_arm(a.file, a.arm)
    own = pairs(rows)
    ids = sorted(own)
    m = lambda xs: sum(xs) / len(xs)
    results = []

    runs = [fit_test([own[i] for i in f], [own[i] for i in t]) for f, t in halves(ids, a.seeds)]
    results.append(("same", f"{a.arm}, other half of the items", len(ids), m([r[0] for r in runs]), m([r[1] for r in runs])))

    category = {r["item_id"]: r["category"] for r in rows}
    for c in sorted(set(category.values())):
        fit = [own[i] for i in ids if category[i] != c]
        test = [own[i] for i in ids if category[i] == c]
        before, after = fit_test(fit, test)
        results.append(("category", f"{a.arm}, category {c!r} left out of the fit", len(test), before, after))

    other = pairs(load_arm(a.file, a.other))
    both = [i for i in ids if i in other]
    moved = [fit_test([own[i] for i in f], [other[i] for i in t]) for f, t in halves(both, a.seeds)]
    kept = [fit_test([other[i] for i in f], [other[i] for i in t]) for f, t in halves(both, a.seeds)]
    results.append(("model", f"{a.arm} correction used on {a.other}", len(both), m([r[0] for r in moved]), m([r[1] for r in moved])))
    results.append(("model", f"{a.other} own correction (for comparison)", len(both), m([r[0] for r in kept]), m([r[1] for r in kept])))

    print(f"{a.file.name}: held-out ECE before and after an isotonic correction "
          f"(halves: {a.seeds} seeds x 2 folds)")
    print(f"  {'case':9s} {'fit and test':55s} {'n':>5s} {'raw':>6s} {'fixed':>6s}")
    for kind, name, n, before, after in results:
        print(f"  {kind:9s} {name:55s} {n:5d} {before:6.3f} {after:6.3f}")

    print("")
    print("In plain words:")
    for kind, name, n, before, after in results:
        if "for comparison" in name:
            continue
        if after > before:
            verdict = "made it WORSE"
        elif after < before / 4:
            verdict = "fixed most of it"
        else:
            verdict = "helped, but left part of the error"
        print(f"  {name}: off by {before:.3f} before, {after:.3f} after. The correction {verdict}.")
    print("  A correction belongs to the model and the question it was fitted on. Check it")
    print("  on answers it was not fitted on before you trust it somewhere new.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
