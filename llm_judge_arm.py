#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 George Kastanis
"""D3code calibration study, LLM-judge arm (the comparison arm).

Same sampled items as jev_arm.py, same output shape, so metrics.py scores
both. The judge is a chat model driven through the claude CLI, asked for the
SAME quantities Jev returns:
a probability that a typical reader finds the message offensive, one per
region, and a 0-4 severity. It must answer as JSON; a parse failure is an
error row, not a guess.

Usage:
    python3 llm_judge_arm.py --data DIR --sample-in sample300.json --out sonnet.jsonl \
        [--model sonnet] [--workers 3] [--limit 100]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from jev_arm import REGIONS, load, human_truth

PROMPT = """You are estimating how a large, balanced panel of ordinary readers from eight
world regions would rate a short online message for offensiveness on a 0-4 scale
(0 not offensive at all, 1 slightly, 2 moderately, 3 very, 4 extremely). A reader
counts as finding it "offensive" when they rate it 2 or higher.

Message:
<<<
{text}
>>>

Return ONLY a JSON object, no prose, with these keys:
  "p_offensive": probability (0.0-1.0) that a typical reader finds it offensive
  "p_region": object mapping each of these exact region names to that probability
              for a typical reader living there: {regions}
  "severity": your estimate of the panel's MEAN raw rating, a number from 0.0 to 4.0
Be numerically honest: use the full 0-1 range, do not round to 0 or 1 unless you
are sure the panel would be unanimous."""


def parse(raw: str) -> dict | None:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    p = d.get("p_offensive")
    if not isinstance(p, (int, float)):
        return None
    return d


def run_claude(prompt: str, model: str | None) -> dict:
    """Ask the judge one question, from an empty working directory.

    The judge must see nothing but the prompt. `claude` picks up CLAUDE.md and
    AGENTS.md from its working directory, and `--setting-sources ""` does not
    suppress those, so running it from wherever the operator happens to stand
    would quietly feed project instructions into the judge and make two runs of
    this arm incomparable. It therefore runs in a fresh empty temp directory.
    """
    cmd = ["claude", "-p", "-"]
    if model:
        cmd += ["--model", model]
    cmd += ["--no-session-persistence", "--permission-mode", "auto",
            "--output-format", "json", "--setting-sources", "", "--strict-mcp-config"]
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    try:
        with tempfile.TemporaryDirectory(prefix="d3code-judge-") as sandbox:
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                                  timeout=300, env=env, cwd=sandbox)
    except FileNotFoundError as exc:
        raise RuntimeError("claude CLI not found; install and log in to the claude CLI") from exc
    except subprocess.TimeoutExpired:
        return {"response": "", "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
    raw = proc.stdout.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"result": raw}
    if isinstance(data, list):
        data = next((item for item in data if isinstance(item, dict)
                     and item.get("type") == "result"), {})
    if not isinstance(data, dict):
        data = {}
    usage = data.get("usage") or {}
    return {"response": data.get("result", ""),
            "cost_usd": data.get("total_cost_usd", 0.0) or 0.0,
            "input_tokens": usage.get("input_tokens", 0) or 0,
            "output_tokens": usage.get("output_tokens", 0) or 0}


def ask(item: dict, truth: dict, model: str | None) -> dict:
    prompt = PROMPT.format(text=item["text"], regions=json.dumps(REGIONS))
    t = time.time()
    res = run_claude(prompt, model)
    d = parse(res.get("response") or "")
    base = {"item_id": item["item_id"], "category": item["category"], "text": item["text"], "human": truth,
            "elapsed": round(time.time() - t, 2), "cost_usd": res.get("cost_usd", 0.0),
            "input_tokens": res.get("input_tokens", 0), "output_tokens": res.get("output_tokens", 0)}
    if d is None:
        return {**base, "error": f"unparseable judge output: {(res.get('response') or '')[:200]!r}"}
    preg = d.get("p_region") or {}
    return {**base, "model": {"p_offensive": float(d["p_offensive"]),
                              "p_region": {r: (float(preg[r]) if isinstance(preg.get(r), (int, float)) else None) for r in REGIONS},
                              "severity_score": float(d["severity"]) if isinstance(d.get("severity"), (int, float)) else None}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--sample-in", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="first N of the sample (0 = all)")
    a = ap.parse_args()
    if shutil.which("claude") is None:
        ap.error("claude CLI not found; install and log in to the claude CLI")

    items, by_item = load(a.data)
    order = json.loads(a.sample_in.read_text())
    by_id = {i["item_id"]: i for i in items}
    sample = [by_id[i] for i in order if i in by_id and i in by_item]
    if a.limit:
        sample = sample[:a.limit]
    done = set()
    if a.out.exists():
        for line in a.out.read_text().splitlines():
            try:
                done.add(json.loads(line)["item_id"])
            except Exception:
                pass
    todo = [i for i in sample if i["item_id"] not in done]
    print(f"{len(sample)} in sample, {len(done)} done, {len(todo)} to judge with claude/{a.model}", file=sys.stderr)
    t0 = time.time()
    cost = 0.0
    errors = 0
    with a.out.open("a") as f, ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(ask, i, human_truth(by_item[i["item_id"]]), a.model) for i in todo]
        for k, fut in enumerate(as_completed(futs), 1):
            row = fut.result()
            cost += float(row.get("cost_usd") or 0)
            errors += 1 if "error" in row else 0
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if k % 10 == 0 or k == len(todo):
                print(f"  {k}/{len(todo)}  ${cost:.2f}  {errors} errors  {time.time()-t0:.0f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
