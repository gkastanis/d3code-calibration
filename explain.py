#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 George Kastanis
"""Turn the measurements into sentences a non-specialist can act on.

Brier, ECE, Spearman and AUC are not self-explanatory, and a repository whose
whole point is "check whether this number means what you think" should not
answer in numbers that need their own decoder. Every script here prints its
tables and then says, in words, what they imply.

Every sentence is derived from the computed values. Nothing is hardcoded, so
the explanations follow the data when it changes.
"""
from __future__ import annotations


def pct(x: float) -> str:
    return f"{round(100 * x)}%"


def worst_bin(table: list[tuple]) -> tuple | None:
    """The populated high-confidence bin with the widest gap: the quotable one.

    `table` rows are (label, n, mean p, mean rate) from metrics.calibration_table.
    """
    rows = [r for r in table if r[1] >= 20 and r[2] >= 0.5]
    return max(rows, key=lambda r: abs(r[2] - r[3])) if rows else None


def explain_scores(s: dict, base: dict, base_p: float, table: list[tuple],
                   label: str = "this model") -> list[str]:
    out = [f"What this says about {label}, in plain words:"]

    w = worst_bin(table)
    if w:
        out.append(f"  When it answered about {w[2]:.2f}, the real answer was yes "
                   f"{pct(w[3])} of the time ({w[1]} items). "
                   f"{'It sounds more certain than it is.' if w[2] > w[3] else 'It undersells itself.'}")

    if s["auc"] is not None:
        out.append(f"  Ordering: take one item that really was a yes and one that really was "
                   f"a no. It scores the yes higher {pct(s['auc'])} of the time. "
                   f"{_auc_word(s['auc'])}")

    better = s["brier"] < base["brier"]
    out.append(f"  Its raw numbers are {'better' if better else 'WORSE'} than ignoring the model "
               f"and always answering {base_p:.2f} "
               f"(error {s['brier']:.3f} against {base['brier']:.3f}).")

    out.append(f"  Threshold at 0.5 and it is right {pct(s['acc@0.5'])} of the time; "
               f"always answering the more common label is right {pct(base['acc@0.5'])}.")

    out.append("  " + _verdict(s, base))
    return out


def _auc_word(auc: float) -> str:
    if auc >= 0.85:
        return "That is a strong ordering."
    if auc >= 0.7:
        return "That is a useful ordering."
    if auc >= 0.6:
        return "That is a weak ordering."
    return "That is close to a coin flip, so the ordering carries little."


def _verdict(s: dict, base: dict) -> str:
    ranks = s["auc"] is not None and s["auc"] >= 0.7
    scaled = s["ece"] < 0.05
    if ranks and scaled:
        return ("Verdict: both the ordering and the number look sound here. "
                "Still set your threshold from your own labelled items.")
    if ranks and not scaled:
        return ("Verdict: use it to RANK, not to threshold. The ordering carries signal "
                "and the number does not mean what it says. Run recal.py to see how "
                "much of that a correction fixes.")
    if not ranks and scaled:
        return ("Verdict: the number is honest but the ordering is weak, so it cannot "
                "separate your cases well. Calibration will not fix that.")
    return ("Verdict: neither the ordering nor the number is carrying much here. "
            "Check the question is reaching the model in a shape it implements.")


def explain_recal(before: dict, after_brier: float, after_ece: float,
                  after_auc: float, base_brier: float) -> list[str]:
    out = ["", "In plain words:"]
    out.append(f"  Before correcting: the probabilities were off by {before['ece']:.3f} on average.")
    out.append(f"  After fitting a correction on half the items and scoring the other half: "
               f"{after_ece:.3f}.")
    out.append(f"  The ordering barely moved ({before['auc']:.3f} to {after_auc:.3f}), which is "
               f"expected. A correction relabels the numbers, it never reorders the items.")
    if after_brier < base_brier:
        out.append(f"  Corrected, it now beats always guessing the average "
                   f"({after_brier:.3f} against {base_brier:.3f}).")
        out.append("  Verdict: the problem was the SCALE, not the signal. That is the fixable kind. "
                   "Run recal_curve.py to see how many labels it would take.")
    else:
        out.append(f"  Even corrected it does not beat always guessing the average "
                   f"({after_brier:.3f} against {base_brier:.3f}).")
        out.append("  Verdict: the problem is the ORDERING, which a correction cannot fix. "
                   "A different model, prompt or question shape might.")
    return out


def explain_curve(rows: list[tuple], raw_brier: float, base_brier: float) -> list[str]:
    """`rows` are (n_fit, brier, ece) at increasing fit-set sizes."""
    if not rows:
        return []
    best = min(rows, key=lambda r: r[1])
    first = rows[0]
    ceiling = raw_brier - best[1]          # the most this correction ever removes
    got = raw_brier - first[1]             # what the smallest fit set already removes
    out = ["", "In plain words:"]
    out.append(f"  Labelling {first[0]} examples removes {pct(got / raw_brier)} of the error. "
               f"The most this correction ever removes, at {best[0]} examples, is "
               f"{pct(ceiling / raw_brier)}.")
    if ceiling > 0:
        out.append(f"  So {first[0]} examples already buy {pct(got / ceiling)} of everything "
                   f"available. The curve is close to flat from the start: labelling ten times "
                   f"more is not worth ten times as much.")
    out.append("  Read the table for the size you can actually afford. And run this on labels "
               "from your own task: this curve is one dataset correcting itself, which is the "
               "easiest case there is.")
    return out


def explain_fanout(mean_change: float, flips: int, n: int,
                   noise: float | None) -> list[str]:
    out = ["", "In plain words:"]
    out.append(f"  Asking the questions together instead of one at a time moved each answer "
               f"by {mean_change:.4f} on average.")
    if noise is not None:
        if mean_change <= noise * 1.2:
            out.append(f"  Asking the SAME question twice moves it {noise:.4f}, so batching "
                       f"changes the answers no more than ordinary run-to-run wobble does. "
                       f"Batch for speed and cost, it is not costing you accuracy.")
        else:
            out.append(f"  Asking the same question twice moves it only {noise:.4f}, so "
                       f"batching is doing something beyond ordinary wobble. Do not batch "
                       f"without checking.")
    if flips:
        out.append(f"  It is not identical though: {flips} of {n} answers crossed the 0.5 line, "
                   f"{pct(flips / n)}. For a pass/fail check that is a real flip rate.")
    else:
        out.append("  No answer crossed the 0.5 line, so no pass/fail verdict changed.")
    return out


def explain_intervals(rows: list[tuple], a: str, b: str) -> list[str]:
    """`rows` are (metric, diff, lo, hi)."""
    real = [r for r in rows if r[2] > 0 or r[3] < 0]
    noise = [r for r in rows if not (r[2] > 0 or r[3] < 0)]
    out = ["", "In plain words:"]
    if real:
        out.append(f"  Differences big enough to believe on this sample: "
                   f"{', '.join(r[0] for r in real)}.")
    if noise:
        out.append(f"  Differences this sample cannot distinguish from zero: "
                   f"{', '.join(r[0] for r in noise)}. "
                   f"Do not report {a} as beating {b} on those.")
    if not noise:
        out.append("  Every difference here holds up.")
    out.append("  An interval that crosses zero means the two arms might be equal, "
               "or the other way round, and this many items cannot tell.")
    return out
