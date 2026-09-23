#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 George Kastanis
"""Score any D3code arm file (jsonl from jev_arm.py or llm_judge_arm.py).

Ground truth per item: human agreement rate (fraction of raters saying
offensive) overall and per region, plus the mean raw 0-4 rating.

Metrics (no numpy, stdlib only):
  brier      mean (p - rate)^2 against the human RATE (a probability target,
             lower is better; a perfectly calibrated oracle scores the
             irreducible rater variance, not 0)
  brier_maj  mean (p - majority)^2 against the majority label (0/1)
  ece        expected calibration error in 10 equal-width bins vs the rate
  spearman   rank correlation between p and rate
  auc        p as a ranker for majority label (rate >= 0.5)
  acc@0.5    accuracy of p >= 0.5 vs majority
Baselines: constant base rate (mean human rate over the sample).
Per-region: the same for region questions vs region rates (only items with
>= 2 raters in that region). Severity: Spearman of score vs mean raw rating.

Usage: python3 metrics.py ARM.jsonl [ARM2.jsonl ...] [--label NAME ...] [--arm NAME]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import explain  # noqa: E402


def rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    return ranks


def spearman(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3:
        return None
    ra, rb = rank(a), rank(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else None


def auc(p: list[float], y: list[int]) -> float | None:
    pos = [pi for pi, yi in zip(p, y) if yi == 1]
    neg = [pi for pi, yi in zip(p, y) if yi == 0]
    if not pos or not neg:
        return None
    wins = 0.0
    for a in pos:
        for b in neg:
            wins += 1.0 if a > b else (0.5 if a == b else 0.0)
    return wins / (len(pos) * len(neg))


def ece(p: list[float], rate: list[float], bins: int = 10) -> float:
    tot = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, pi in enumerate(p) if (lo <= pi < hi) or (b == bins - 1 and pi == 1.0)]
        if not idx:
            continue
        mp = sum(p[i] for i in idx) / len(idx)
        mr = sum(rate[i] for i in idx) / len(idx)
        tot += len(idx) / len(p) * abs(mp - mr)
    return tot


def calibration_table(p: list[float], rate: list[float], bins: int = 10) -> list[tuple]:
    rows = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, pi in enumerate(p) if (lo <= pi < hi) or (b == bins - 1 and pi == 1.0)]
        if idx:
            rows.append((f"{lo:.1f}-{hi:.1f}", len(idx), sum(p[i] for i in idx) / len(idx), sum(rate[i] for i in idx) / len(idx)))
    return rows


def score(p: list[float], rate: list[float]) -> dict:
    maj = [1 if r >= 0.5 else 0 for r in rate]
    return {
        "n": len(p),
        "brier": sum((a - b) ** 2 for a, b in zip(p, rate)) / len(p),
        "brier_maj": sum((a - b) ** 2 for a, b in zip(p, maj)) / len(p),
        "ece": ece(p, rate),
        "spearman": spearman(p, rate),
        "auc": auc(p, maj),
        "acc@0.5": sum(1 for a, m in zip(p, maj) if (a >= 0.5) == (m == 1)) / len(p),
    }


def fmt(d: dict) -> str:
    def f(x):
        return "  n/a" if x is None else f"{x:5.3f}"
    return (f"n={d['n']:<4} brier={f(d['brier'])} brier_maj={f(d['brier_maj'])} ece={f(d['ece'])} "
            f"spearman={f(d['spearman'])} auc={f(d['auc'])} acc@0.5={f(d['acc@0.5'])}")


def load_arm(path: Path, arm: str | None = None) -> list[dict]:
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    present = sorted({r["arm"] for r in rows if "arm" in r})
    if arm is not None:
        rows = [r for r in rows if r.get("arm") == arm]
        if not rows:
            raise SystemExit(f"{path.name}: no rows for arm {arm!r}. "
                             f"Available: {', '.join(present) or '(none)'}")
    elif len(present) > 1:
        # results-compact.jsonl holds every arm in one file, and the dedup below
        # keeps the first row per item_id. Scoring it unfiltered would silently
        # report whichever arm sorts first, under whatever label the caller
        # passed. Refuse rather than answer the wrong question quietly.
        raise SystemExit(f"{path.name} holds {len(present)} arms; pass --arm to pick one.\n"
                         f"Available: {', '.join(present)}")
    # D3code's items file repeats 34 item_ids; keep the first scored row per id.
    seen, out = set(), []
    for r in rows:
        if "model" in r and r["model"].get("p_offensive") is not None and r["item_id"] not in seen:
            seen.add(r["item_id"]); out.append(r)
    return out


def report(path: Path, label: str, arm: str | None = None) -> None:
    rows = load_arm(path, arm)
    if not rows:
        print(f"{label}: no scored rows in {path}")
        return
    p = [float(r["model"]["p_offensive"]) for r in rows]
    rate = [float(r["human"]["rate"]) for r in rows]
    base = sum(rate) / len(rate)
    overall = score(p, rate)
    base_s = score([base] * len(rate), rate)
    print(f"\n=== {label} ({path.name}) ===")
    print("overall      ", fmt(overall))
    print("base-rate    ", fmt(base_s), f"(constant p={base:.3f})")
    el = [r.get("elapsed", 0) for r in rows]
    cost = sum(float(r.get("cost_usd", 0) or 0) for r in rows)
    print(f"latency: mean {sum(el)/len(el):.2f}s  median {sorted(el)[len(el)//2]:.2f}s   cost: ${cost:.3f} total, ${cost/len(rows):.4f}/item"
          if cost else f"latency: mean {sum(el)/len(el):.2f}s  median {sorted(el)[len(el)//2]:.2f}s   cost: not reported by this arm")
    print("calibration (bin, n, mean p, mean human rate):")
    table = calibration_table(p, rate)
    for b, n, mp, mr in table:
        print(f"   {b}  n={n:<4} p={mp:.2f}  human={mr:.2f}  gap={mp-mr:+.2f}")
    print()
    for line in explain.explain_scores(overall, base_s, base, table, label):
        print(line)
    print()
    # per category
    cats = sorted({r["category"] for r in rows})
    for c in cats:
        idx = [i for i, r in enumerate(rows) if r["category"] == c]
        print(f"category {c:<13}", fmt(score([p[i] for i in idx], [rate[i] for i in idx])))
    # per region
    preg = rows[0]["model"].get("p_region") or {}
    if preg:
        print("regions (region question vs that region's raters, items with >= 2 region raters):")
        agg_p, agg_r = [], []
        for reg in preg:
            pp, rr = [], []
            for r in rows:
                h = r["human"]["regions"].get(reg) or {}
                pv = (r["model"].get("p_region") or {}).get(reg)
                if h.get("n", 0) >= 2 and h.get("rate") is not None and pv is not None:
                    pp.append(float(pv)); rr.append(float(h["rate"]))
            if pp:
                s = score(pp, rr)
                # does the model MOVE with region? mean p per region vs mean human rate per region
                print(f"   {reg:<24} mean p={sum(pp)/len(pp):.2f} mean human={sum(rr)/len(rr):.2f}  {fmt(s)}")
                agg_p.append(sum(pp) / len(pp)); agg_r.append(sum(rr) / len(rr))
        if len(agg_p) >= 3:
            print(f"   region-level ordering: spearman(mean p, mean human) = {spearman(agg_p, agg_r):.3f} over {len(agg_p)} regions")
    sev = [(float(r["model"]["severity_score"]), float(r["human"]["mean_raw"]))
           for r in rows if r["model"].get("severity_score") is not None and r["human"].get("mean_raw") is not None]
    if sev:
        print(f"severity: spearman(score, mean raw 0-4) = {spearman([a for a,_ in sev],[b for _,b in sev]):.3f}  "
              f"mean score {sum(a for a,_ in sev)/len(sev):.2f} vs mean raw {sum(b for _,b in sev)/len(sev):.2f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("arms", nargs="+", type=Path)
    ap.add_argument("--label", action="append", default=[])
    ap.add_argument("--arm", help="select this arm from a combined JSONL file")
    a = ap.parse_args()
    for i, path in enumerate(a.arms):
        report(path, a.label[i] if i < len(a.label) else path.stem, a.arm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
