#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 George Kastanis
"""Is the fan-out claim a paired comparison, or two aggregates that happen to match?

Asking nine questions in one call versus one question per call, on the same
items, so the difference is per item rather than between two aggregates that
could hide cancelling movement. `--repeat` adds the same-question rerun noise
for scale: a change no bigger than rerunning the identical question is not a
fan-out effect.

Usage:
    python3 fanout_paired.py results-compact.jsonl results-compact.jsonl \\
        --arm jev-300 --single-arm jev-single \\
        --repeat results-compact.jsonl results-compact.jsonl results-compact.jsonl \\
        --repeat-arm jev-100 jev-100-rep2 jev-100-rep3
"""

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import load_arm, score  # noqa: E402
import explain  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fanout", type=Path)
    ap.add_argument("single", type=Path)
    ap.add_argument("--arm", help="fan-out arm in a combined JSONL file")
    ap.add_argument("--single-arm", help="single-question arm in a combined JSONL file")
    ap.add_argument("--repeat", nargs=3, type=Path, metavar=("FIRST", "SECOND", "THIRD"),
                    help="three same-question files for the rerun-noise baseline")
    ap.add_argument("--repeat-arm", nargs=3, metavar=("FIRST", "SECOND", "THIRD"),
                    help="arm names for the three repeat files")
    a = ap.parse_args()
    if a.repeat_arm and not a.repeat:
        ap.error("--repeat-arm requires --repeat")

    fan = {r['item_id']: r for r in load_arm(a.fanout, a.arm)}
    sin = {r['item_id']: r for r in load_arm(a.single, a.single_arm)}
    shared = sorted(set(fan) & set(sin))
    print(f"fan-out rows {len(fan)}, single rows {len(sin)}, shared item_ids {len(shared)}")
    if not shared:
        sys.exit("no overlap: NOT a paired comparison")

    pf = [float(fan[i]['model']['p_offensive']) for i in shared]
    ps = [float(sin[i]['model']['p_offensive']) for i in shared]
    y = [float(fan[i]['human']['rate']) for i in shared]

    sf, ss = score(pf, y), score(ps, y)
    print(f"\non the SAME {len(shared)} items:")
    print(f"  fan-out  brier={sf['brier']:.4f} ece={sf['ece']:.4f} auc={sf['auc']:.4f}")
    print(f"  single   brier={ss['brier']:.4f} ece={ss['ece']:.4f} auc={ss['auc']:.4f}")

    d = [abs(x - z) for x, z in zip(pf, ps)]
    print("\nper-item difference in p:")
    print(f"  identical            {sum(1 for x in d if x == 0)} of {len(d)}")
    print(f"  mean |change|        {statistics.fmean(d):.4f}")
    print(f"  median |change|      {statistics.median(d):.4f}")
    print(f"  max |change|         {max(d):.4f}")
    print(f"  moved more than 0.05 {sum(1 for x in d if x > 0.05)}")
    print(f"  moved more than 0.10 {sum(1 for x in d if x > 0.10)}")
    flips = sum(1 for x, z in zip(pf, ps) if (x >= 0.5) != (z >= 0.5))
    print(f"  crossed the 0.5 line {flips}")
    mean_change = statistics.fmean(d)
    rerun_noise = None

    if a.repeat:
        reps = [load_arm(path, a.repeat_arm[i] if a.repeat_arm else None)
                for i, path in enumerate(a.repeat)]
        maps = [{r['item_id']: float(r['model']['p_offensive']) for r in rr} for rr in reps]
        common = sorted(set(maps[0]) & set(maps[1]) & set(maps[2]))
        noise = []
        for i in common:
            v = [m[i] for m in maps]
            noise += [abs(v[0] - v[1]), abs(v[0] - v[2]), abs(v[1] - v[2])]
        if not noise:
            sys.exit("no overlap among repeat files")
        names = ", ".join(a.repeat_arm) if a.repeat_arm else ", ".join(p.name for p in a.repeat)
        print(f"\nsame-question rerun noise ({names}; {len(common)} items, {len(noise)} pairs):")
        print(f"  identical            {sum(1 for x in noise if x == 0)} of {len(noise)}")
        print(f"  mean |change|        {statistics.fmean(noise):.4f}")
        print(f"  max |change|         {max(noise):.4f}")
        rerun_noise = statistics.fmean(noise)

    for line in explain.explain_fanout(mean_change, flips, len(shared), rerun_noise):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
