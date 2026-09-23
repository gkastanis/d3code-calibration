#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 George Kastanis
"""D3code calibration study, Laya arm.

Laya (github.com/NandhaKishorM/laya, Apache-2.0) is an open-weights System 1
decision engine: ModernBERT-large / mmBERT-base, non-autoregressive, same typed
question shape as TypeSafe's System One (noul / choice / score). It runs local,
so this arm costs nothing and can be rerun by anyone.

Its README already concedes the finding we measured on Jev: "Both checkpoints
are over-confident as shipped. Refitting one temperature per (question type,
option count) on held-out data moves mean ECE 0.466 -> 0.081". This arm checks
that claim on an independent dataset with human agreement rates as truth.

Emits the same row shape as jev_arm.py so metrics.py and recal.py score it
unchanged.

Usage:
    python3 laya_arm.py --data DIR --sample-in sample100.json --out laya100.jsonl
    python3 laya_arm.py --data DIR --n 4590 --seed 1 --out laya_full.jsonl
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import sys
import time
from pathlib import Path

import jev_arm  # load(), human_truth(), questions(), REGIONS

REGIONS = jev_arm.REGIONS


def build(overall_only: bool) -> dict:
    qs = jev_arm.questions()
    return {"overall": qs["overall"]} if overall_only else qs


def engine_for(name: str):
    import laya
    if name == "router" or not hasattr(laya, "Laya"):
        return laya.Router(preload=True)
    return laya.Laya(name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--sample-in", type=Path)
    ap.add_argument("--sample-out", type=Path)
    ap.add_argument("--overall-only", action="store_true")
    ap.add_argument("--checkpoint", default="laya",
                    help="laya | laya-multilingual | laya-typed-decisions | router")
    a = ap.parse_args()

    engine = engine_for(a.checkpoint)

    items, by_item = jev_arm.load(a.data)
    items = [i for i in items if i["item_id"] in by_item]
    if a.sample_in:
        want = set(json.loads(a.sample_in.read_text()))
        sample = [i for i in items if i["item_id"] in want]
    else:
        rng = random.Random(a.seed)
        by_cat: dict = collections.defaultdict(list)
        for i in items:
            by_cat[i["category"]].append(i)
        sample = []
        for cat, pool in by_cat.items():
            k = max(1, round(a.n * len(pool) / len(items)))
            sample += rng.sample(pool, min(k, len(pool)))
        rng.shuffle(sample)
        sample = sample[:a.n]
    if a.sample_out:
        a.sample_out.write_text(json.dumps([i["item_id"] for i in sample]))

    done = set()
    if a.out.exists():
        for line in a.out.read_text().splitlines():
            try:
                done.add(json.loads(line)["item_id"])
            except Exception:
                pass
    todo = [i for i in sample if i["item_id"] not in done]
    print(f"{len(sample)} sampled, {len(done)} done, {len(todo)} to ask "
          f"(checkpoint={a.checkpoint})", file=sys.stderr)

    qs = build(a.overall_only)
    t0 = time.time()
    errors = 0
    with a.out.open("a") as f:
        for k, item in enumerate(todo, 1):
            truth = jev_arm.human_truth(by_item[item["item_id"]])
            t = time.time()
            try:
                res = engine.predict({"message": item["text"]}, qs)
                ans = res["answers"]
                sev = ans.get("severity", {})
                row = {"item_id": item["item_id"], "category": item["category"],
                       "text": item["text"], "human": truth,
                       "model": {"p_offensive": ans.get("overall", {}).get("noul"),
                                 "p_region": {r: ans.get(f"region:{r}", {}).get("noul")
                                              for r in REGIONS},
                                 "severity_score": sev.get("score"),
                                 "severity_confidence": sev.get("confidence"),
                                 "severity_probabilities": sev.get("distribution")
                                 or sev.get("probabilities")},
                       "elapsed": round(time.time() - t, 3)}
            except Exception as e:
                errors += 1
                row = {"item_id": item["item_id"], "category": item["category"], "human": truth,
                       "error": f"{type(e).__name__}: {e}", "elapsed": round(time.time() - t, 3)}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if k % 25 == 0 or k == len(todo):
                print(f"  {k}/{len(todo)} ({errors} errors, {time.time() - t0:.0f}s, "
                      f"{(time.time() - t0) / k:.2f}s/item)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
