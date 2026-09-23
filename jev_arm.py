#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 George Kastanis
"""D3code calibration study, Jev arm.

D3code (google-research-datasets/D3code, CC-BY 4.0): 4,590 Jigsaw items, each
rated offensive/not by ~24 people balanced across eight geo-cultural regions.
That gives every item a human agreement rate, overall and per region: ground
truth for a PROBABILITY, which is what a calibrated yes/no model claims to give.

Per item, one System One call with fan-out questions:
    overall            noul   "Would a typical reader find this message offensive?"
    region:<R> x 8     noul   same, for a typical reader from region R
    severity           score  0..4 (D3code's raw scale), compared to the mean raw rating

Output: one JSON line per item with the human rates and the model's answers.
Metrics are computed by metrics.py so the same file scores any arm.

Usage:
    python3 jev_arm.py --data DIR --n 300 --seed 7 --out jev.jsonl [--workers 4]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import systemone

REGIONS = ["North America", "Western Europe", "Latin America", "Arab Culture",
           "Sub Saharan Africa", "Indian Cultural Sphere", "Sinosphere", "Oceania"]
SEVERITY_LEVELS = ["Not offensive at all", "Slightly offensive", "Moderately offensive",
                   "Very offensive", "Extremely offensive"]


def load(data: Path) -> tuple[list[dict], dict]:
    items = list(csv.DictReader(open(data / "d3-items.csv", encoding="utf-8")))
    raters = {r["rater_id"]: r for r in csv.DictReader(open(data / "d3-raters.csv", encoding="utf-8"))}
    by_item: dict = collections.defaultdict(list)
    for r in csv.DictReader(open(data / "d3-ratings.csv", encoding="utf-8")):
        if r["rating_binary"] in ("", "na", "NA") or r["rating_raw"] in ("", "-1"):
            continue
        reg = raters.get(r["rater_id"], {}).get("Region", "")
        by_item[r["item_id"]].append((int(float(r["rating_binary"])), int(r["rating_raw"]), reg))
    return items, by_item


def human_truth(votes: list[tuple]) -> dict:
    n = len(votes)
    out = {"n": n, "rate": sum(b for b, _, _ in votes) / n if n else None,
           "mean_raw": sum(raw for _, raw, _ in votes) / n if n else None, "regions": {}}
    for reg in REGIONS:
        rv = [b for b, _, r in votes if r == reg]
        out["regions"][reg] = {"n": len(rv), "rate": (sum(rv) / len(rv)) if rv else None}
    return out


def questions() -> dict:
    q = {"overall": {"type": "noul",
                     "instructions": "Would a typical reader find this message offensive?",
                     "criteria": {"true": "Most readers would call it offensive (rating 2 or more on a 0-4 scale)",
                                  "false": "Most readers would call it not or only slightly offensive (0 or 1)"}}}
    for reg in REGIONS:
        q[f"region:{reg}"] = {"type": "noul",
                              "instructions": f"Would a typical reader living in the {reg} region find this message offensive?",
                              "criteria": {"true": f"Most readers from {reg} would rate it 2 or more on a 0-4 offensiveness scale",
                                           "false": f"Most readers from {reg} would rate it 0 or 1"}}
    q["severity"] = {"type": "score",
                     "instructions": "How offensive is this message to a typical reader?",
                     "criteria": SEVERITY_LEVELS}
    return q


OVERALL_ONLY = False  # set by --overall-only: one noul per call, no region fan-out, no score


def ask(item: dict, truth: dict, retries: int = 4) -> dict:
    state = {"message": item["text"]}
    qs = questions()
    if OVERALL_ONLY:
        qs = {"overall": qs["overall"]}
    t = time.time()
    last = None
    for attempt in range(retries + 1):
        try:
            answers = systemone.ask(state, qs, retries=0, timeout=60)
            break
        except systemone.SystemOneUnavailable as e:
            last = str(e)
            if attempt == retries:
                return {"item_id": item["item_id"], "category": item["category"], "human": truth,
                        "error": last, "elapsed": round(time.time() - t, 2)}
            time.sleep(min(30, 2 ** attempt + random.random()))
    p_reg = {reg: answers.get(f"region:{reg}", {}).get("noul") for reg in REGIONS}
    sev = answers.get("severity", {})
    return {"item_id": item["item_id"], "category": item["category"], "text": item["text"],
            "human": truth,
            "model": {"p_offensive": answers.get("overall", {}).get("noul"), "p_region": p_reg,
                      "severity_score": sev.get("score"), "severity_confidence": sev.get("confidence"),
                      "severity_probabilities": sev.get("probabilities")},
            "elapsed": round(time.time() - t, 2)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--sample-out", type=Path, help="write the sampled item ids (shared with other arms)")
    ap.add_argument("--sample-in", type=Path, help="reuse a sample file instead of drawing one")
    ap.add_argument("--overall-only", action="store_true",
                    help="one noul per call (no region fan-out, no severity): tests whether fan-out shifts p")
    a = ap.parse_args()
    global OVERALL_ONLY
    OVERALL_ONLY = a.overall_only

    items, by_item = load(a.data)
    items = [i for i in items if i["item_id"] in by_item]
    if a.sample_in:
        want = set(json.loads(a.sample_in.read_text()))
        sample = [i for i in items if i["item_id"] in want]
    else:
        rng = random.Random(a.seed)
        by_cat: dict = collections.defaultdict(list)
        for i in items:
            by_cat[i["category"]].append(i)
        # stratified by category, proportional
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
    print(f"{len(sample)} sampled, {len(done)} already done, {len(todo)} to ask", file=sys.stderr)
    t0 = time.time()
    errors = 0
    with a.out.open("a") as f, ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(ask, i, human_truth(by_item[i["item_id"]])): i for i in todo}
        for k, fut in enumerate(as_completed(futs), 1):
            row = fut.result()
            errors += 1 if "error" in row else 0
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if k % 25 == 0 or k == len(todo):
                print(f"  {k}/{len(todo)} ({errors} errors, {time.time() - t0:.0f}s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
