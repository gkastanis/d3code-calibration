# Limits, corrections and a dead end

What this study does not show, two claims an earlier draft got wrong, and one
model that was tried and dropped. Read this before quoting any number here.

[Back to the README](../README.md)

## A separate Drupal probe exposed a question-format mismatch

> **The numbers in this section come from a separate experiment that is not in
> this repository**, and cannot be reproduced from `results-compact.jsonl`. They
> are reported here because they are the reason the conclusions above are
> hedged. The probe runs against the `semantic_yes` rubric check in
> [drupal/ai_best_practices](https://www.drupal.org/project/ai_best_practices),
> its Drupal-specific rubrics and its fixtures, none of which belong in a study
> of D3code. The D3code results in this README are reproducible here. The Needle smoke scripts were not kept.

The probe runs Laya through the `semantic_yes` fixtures and paraphrase probes
from that sibling experiment (Drupal GitLab answers: "does this response explain
that the fork must be provisioned before the first push?"). It reuses the
`asker` seam already in that check, so swapping the provider is one function and
no rubric changes.

The first run of this looked catastrophic for Laya: every one of the thirteen
inputs came back between 0.56 and 0.75, right or wrong. That was our question
shape, not the model. The rubric check builds its question with `criteria` as a
sibling key of `instructions`, which is Jev's documented shape. Laya's docs use
`criteria` for `choice` (label to description) and `score` (a list of levels),
but their `noul` example carries `instructions` only, and we send
`{"true": ..., "false": ...}`.

What Laya does with that key is **not established**. It does not ignore it: with
the key versus without it, all thirteen answers change, mean move 0.17, largest
0.33. It accepts the call either way and never errors. All we can say is that
sending `criteria` on a `noul` collapses its output into a 0.19-wide band.

A follow-up run asked the same thirteen inputs three ways:

| how the question is built | wrong | range of answers | spread |
|---|---|---|---|
| `criteria` as its own key (the bug) | 7 of 13 | 0.56 to 0.75 | 0.19 |
| criteria folded into `instructions` | **4 of 13** | 0.18 to 0.93 | 0.75 |
| criteria dropped entirely | 5 of 13 | 0.29 to 0.93 | 0.64 |

Folded in, Laya discriminates. So the fair comparison, on the thirteen:

| | Jev | Laya (criteria folded) | the keyword check it replaced |
|---|---|---|---|
| fail fixtures correctly rejected | 3 of 3 | 2 of 3 | 3 of 3 |
| paraphrase probes wrong | **0 of 7** | 3 of 7 | 4 of 7 |
| all thirteen wrong | **0 of 13** | 4 of 13 | n/a |

Jev made fewer errors on these thirteen questions. Laya is no longer useless on them,
and the original "soft yes to everything" reading was an artifact.

### Corrections to the earlier draft

Two claims an earlier draft of this section made that did not survive checking,
recorded so they do not get repeated:

- *"Laya is a content-moderation model, calibrated on its home turf."* Not
  supported. The model card describes a general typed-decision model whose
  worked examples are email triage, ticket routing and intent classification;
  moderation is one preset among `email_questions`, `triage_questions`,
  `router_questions` and `guard_questions`. D3code being a moderation set does
  not make Laya a moderation model.
- *"Laya says a soft yes to everything."* An artifact of the bug above.

Still untested, now that the harness confound is out of the way: whether the
residual gap on our questions is about question shape (D3code asks about a text,
our rubrics ask a question *about* a response), input length (one sentence
versus a whole markdown answer), or checkpoint (`laya_arm.py` takes
`--checkpoint`; only the router default was run).

## What this changed in our own grader

These are the practical conclusions for the `semantic_yes` rubric check in
drupal/ai_best_practices, which is what started the study. They are listed here
rather than in the README because they are specific to that grader.

- Use the number as a **ranker**, and set the threshold from labelled data, not
  from 0.5. On D3code the crowd-majority boundary sits near Jev p = 0.9, not 0.5.
- If the rubric needs a probability that means what it says, put a calibration
  map in front of it. Measured: 150 labelled items remove 81 percent of the raw
  Brier error and land within 6 percent of what 2,000 items give. See
  `recal_curve.py`.
- The per-region result says: do not expect Jev to answer "for whom" questions
  differently from the global one.
- **The rubric check emits a Jev-shaped question and nothing checks that the
  provider implements it.** Sending `criteria` on a `noul` degrades Laya badly
  and silently. Any grader that swaps providers behind the `asker` seam
  needs each provider to declare which keys it honours, and to fold or fail on
  the rest, rather than degrade quietly. This is the one concrete code change
  this study asks for.
- **Before swapping the provider, re-run the fixtures.** The `asker` argument
  makes the swap a one-liner, which is exactly why it needs a gate. A provider
  is qualified per eval set, not once.
- A spread check is cheap insurance in the grader: if every `semantic_yes` in a
  run lands inside a narrow band, either the model has no opinion about this
  rubric or it is not receiving the whole question. Either way the pass rate is
  meaningless. That check would have caught the bug above in one run. Not
  implemented yet.

## Limits of the study

- One dataset, one domain (offensiveness), English. The over-confidence pattern
  may not transfer to "does this Drupal answer make the point" questions; there
  the fixture and probe results from the sibling experiment were well
  separated, but that was 13 items. The Laya result is the concrete warning
  that a rank on this dataset does not transfer: treat every table here as a
  measurement of D3code, not of the models.
- Sonnet arm is 100 items; Jev and Laya arms are the full set. The three-way
  head-to-head table is on the shared 100 only.
- The full Laya arm asked the overall question alone, the full Jev arm used the
  fan-out. Fan-out made no difference for Jev (below) and the Laya 100 ran both
  ways, but this is not a controlled comparison of the two protocols.
- Laya ran on CPU here, so its latency column measures this box, not the model.
  Its README reports 33 ms per question on a T4.
- The prompt to Sonnet asked for the same quantities but is a different task
  framing (write JSON) from Jev's typed question. A fairer LLM baseline would
  sample many completions and average.
- TypeSafe publishes no price, so the cost column is one-sided.
- Item texts are offensive by construction; `results-compact.jsonl` here omits
  them and keeps only ids, human rates and model outputs. Re-fetch texts from
  D3code by `item_id`.

## Appendix: why Needle was not an arm

Needle 3 (`cactus-needle` 3.0.2, Apache-2.0) is an 8-29 MB on-device model
for tool calls and structured extraction that advertises "a calibrated
confidence score from a learned head". We tried it as a free local arm.
It is the wrong instrument for a judgment task:

- Classification runs through extraction with an enum. With grounding on
  (the default) it rejected a 0-4 severity as "not grounded in the input":
  it extracts facts stated in the text, it does not form opinions about it.
- Given the bare message it treated the text as a request to route to a tool
  and returned no label on 8 of 10 items. Its confidence did not track
  offensiveness (0.66 on "It's about time", 0.21 on a clearly offensive line).
- With a moderator system prompt and grounding off it labelled 8 of 10 and got
  4 of those 8 right: a coin flip on items the crowd agreed on at 0.7+ or 0.1-.
- Its confidence is one number per call (min of a calibration head and the
  decode probability of the call), so there is no per-label probability to
  calibrate even if the labels were good.

The smoke scripts were not kept; the conclusion is that
Needle's calibration claim is about extraction correctness, a different thing
from a calibrated judgment. No arm was run.
