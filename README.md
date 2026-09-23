# Does that probability mean anything?

A model hands you 0.85. Is the answer yes about 85% of the time, or is 0.85 just
a number that sorts above 0.84?

This repository is two things. Mostly it is **a small stdlib-only tool for
answering that question about any model, on your own data**. It is also the
worked example that produced it: TypeSafe's Jev and the open-weights Laya,
measured against 150,000 human ratings.

The tool asks two questions your accuracy number cannot:

- **Is the problem the scale or the ranking?** A model can order your items
  correctly and still report absurd probabilities. That is repairable. A model
  that orders them wrongly is not: no relabelling of the numbers can reorder
  them. `recal.py` tells you which one you have.
- **How many labelled examples would the repair take?** `recal_curve.py` gives
  you the curve rather than a shrug. Here, 25 examples removed 77% of the error
  and 150 got within 6% of what 2,000 gave.

Feed either script a list of *(what the model said, what was actually true)*
pairs and it answers. Nothing in them is specific to these models, this dataset,
or this task.

## Install and run

Python 3.10 or newer. The scoring path is standard library only, so the included
results can be checked with no API key, no model download and no pip install:

```bash
python3 metrics.py  results-compact.jsonl --arm jev-full  --label jev
python3 metrics.py  results-compact.jsonl --arm laya-full --label laya
python3 recal.py    results-compact.jsonl --arm jev-full
python3 intervals.py results-compact.jsonl --arm jev-full --vs laya-full
```

`results-compact.jsonl` holds every row of every arm, keyed by an `arm` field,
with the item texts removed. Every table below is reproducible from it; the
exact commands are under [Reproduce](#reproduce). Running a model fresh needs
more: `pip install laya` for the local Laya arm, a TypeSafe API key for Jev, the
`claude` CLI for the Sonnet arm, and the original D3code download for the item
texts this repository does not republish.

## The worked example

Jev returns a probability for a yes/no question instead of text, and the pitch
is that the number is calibrated. The question this study started from was
narrow and practical: an eval rubric of ours thresholds on that number, so when
Jev says 0.8, is the answer yes about 80% of the time?

Our own repository could not answer it. Five traces, eight labels. D3code can.

**Short answer.** No, and the shape of the miss matters more than the fact of
it. Jev's probability is over-confident in one direction, toward yes. It ranks
items well and its scale is wrong, repairably. Laya, the open-weights
alternative, is near-perfectly scaled here with no repair at all but ranks
worse, so after the repair Jev is ahead again. **Scale is cheap to fix and rank
is not.** A published calibration number licenses nothing about your data.

A second lesson came out of getting this wrong in a draft that was nearly
published: we first measured Laya through a question shape it does not
implement, and read the resulting flat answers as "this model has no signal".
See [The finding](#the-finding).

## Ground truth

[D3code](https://github.com/google-research-datasets/D3code) (Google Research,
CC-BY 4.0): 4,590 short online messages from the Jigsaw corpus, each rated for
offensiveness on a 0-4 scale by about 24 people, balanced across eight
geo-cultural regions, 4,309 raters, 150,702 ratings. A rating of 2 or more counts
as "offensive". So every item has a human agreement rate: the fraction of raters
who called it offensive, overall and per region. That fraction is the target a
calibrated probability should track.

34 item ids appear twice in the items file; metrics keep the first scored row per
id, leaving 4,554 items.

## Arms

| Arm | What was asked | Items | Latency | Cost |
|---|---|---|---|---|
| Jev (`jev-latest`), fan-out | one call: overall noul + 8 region nouls + a 0-4 score | 4,554 | 0.69 s mean | not published by TypeSafe |
| Jev, single question | one call: overall noul only | 305 (300 after dedup) | 0.68 s | same |
| Sonnet via `claude -p` | JSON with p_offensive, 8 region p's, severity | 100 | 5.70 s mean | $0.064 per item ($6.40 total; a 30-item repeat cost $0.010 per item, cache warm) |
| Laya (`laya` via `Router`), single question | one call: overall noul only | 4,554 | 0.83 s mean (CPU, no GPU on this box) | free, open weights, runs local |
| Laya, fan-out | overall + 8 region nouls + a 0-4 score | 100 | 5.71 s | free |
| Base rate | constant p = mean human rate | all | 0 | 0 |

Question wording is in `jev_arm.py` and `llm_judge_arm.py`; `laya_arm.py`
imports the Jev arm's question builder so the two models are asked exactly the
same thing. All arms were told the 0-4 scale and that "offensive" means 2 or
more.

## Results

### Overall, full dataset (n = 4,554, both models on every item)

| Metric | Jev raw | Laya raw | Base rate |
|---|---|---|---|
| Brier vs human rate (lower is better) | 0.098 | **0.023** | 0.035 |
| Calibration error (ECE, 10 bins) | 0.251 | **0.033** | 0.000 |
| Spearman(p, human rate) | **0.710** | 0.622 | n/a |
| AUC vs majority label | **0.858** | 0.798 | 0.500 |
| Accuracy at p >= 0.5 | 0.557 | **0.797** | 0.784 |

The two split cleanly: **Jev ranks better, Laya is scaled better.** Jev is the
only arm whose raw probability loses to a constant.

At this sample size every one of those gaps is real. Paired bootstrap, 400
resamples of the 4,554 shared items, scoring both arms on the same resample
(`intervals.py --arm jev-full --vs laya-full`):

| Metric | Jev 95% CI | Laya 95% CI | Jev minus Laya | Excludes zero |
|---|---|---|---|---|
| Brier | 0.095 to 0.101 | 0.022 to 0.024 | +0.074 (+0.071, +0.077) | yes |
| ECE | 0.245 to 0.257 | 0.029 to 0.037 | +0.219 (+0.212, +0.226) | yes |
| Spearman | 0.695 to 0.725 | 0.602 to 0.641 | +0.088 (+0.069, +0.108) | yes |
| AUC | 0.844 to 0.870 | 0.784 to 0.812 | +0.061 (+0.046, +0.076) | yes |
| Accuracy at 0.5 | 0.544 to 0.571 | 0.786 to 0.809 | -0.240 (-0.260, -0.223) | yes |

The 100-item tables below are a different story, and the intervals there are the
reason to read them carefully rather than as a ranking.

Calibration curve, raw:

| Jev p bin | n | mean p | mean human rate | gap |
|---|---|---|---|---|
| 0.0-0.1 | 118 | 0.06 | 0.07 | -0.01 |
| 0.1-0.2 | 294 | 0.15 | 0.13 | +0.02 |
| 0.2-0.3 | 405 | 0.24 | 0.19 | +0.06 |
| 0.3-0.4 | 438 | 0.34 | 0.23 | +0.11 |
| 0.4-0.5 | 377 | 0.44 | 0.27 | +0.17 |
| 0.5-0.6 | 475 | 0.55 | 0.29 | +0.25 |
| 0.6-0.7 | 531 | 0.64 | 0.33 | +0.31 |
| 0.7-0.8 | 585 | 0.75 | 0.38 | +0.37 |
| 0.8-0.9 | 791 | 0.85 | 0.45 | +0.39 |
| 0.9-1.0 | 540 | 0.93 | 0.58 | +0.35 |

Reading: below 0.2 the number is honest. Above 0.5 it is not. When Jev says 0.85,
45% of people agreed. It ranks well and reads strict: the number behaves like
one severe rater, not like the average of 24.

### Head to head on the same 100 items

| Metric | Jev raw | Sonnet raw | Laya raw | Base rate |
|---|---|---|---|---|
| Brier vs rate | 0.104 | 0.037 | **0.021** | 0.029 |
| ECE | 0.262 | 0.115 | **0.035** | 0.000 |
| Spearman | 0.608 | 0.573 | 0.576 | n/a |
| AUC | 0.836 | 0.799 | 0.841 | 0.500 |
| Latency | 0.70 s | 5.70 s | 5.71 s (CPU) | |

Sonnet is closer to the crowd's scale than Jev. Laya is closer than either, and
is the only arm whose raw probability beats a constant base rate. Of the two
paid arms, neither raw number does.

**Do not read the Spearman and AUC rows as a ranking of these three models.** At
100 items they are noise. Paired bootstrap, 2,000 resamples
(`intervals.py --arm jev-100 --vs sonnet-100`, and the same against
`laya-100`):

| Difference on the 100 | Jev minus Sonnet | Jev minus Laya |
|---|---|---|
| Brier | +0.067 (+0.050, +0.088) **real** | +0.083 (+0.062, +0.106) **real** |
| ECE | +0.146 (+0.116, +0.178) **real** | +0.227 (+0.178, +0.265) **real** |
| Spearman | +0.036 (-0.095, +0.158) noise | +0.032 (-0.112, +0.173) noise |
| AUC | +0.037 (-0.045, +0.126) noise | -0.005 (-0.120, +0.109) noise |
| Accuracy at 0.5 | -0.180 (-0.280, -0.080) **real** | -0.300 (-0.440, -0.170) **real** |

So on 100 items the *calibration* differences are solid and the *ranking*
differences are not distinguishable from zero. Jev's ranking advantage is real,
but it takes the full 4,554 items to see it. Jev's individual AUC interval here
is 0.742 to 0.913, which is most of the useful range.

This is the ordinary arithmetic of small samples, and it is worth stating
plainly in a study whose subject is numbers that look more certain than they
are.

### Is it the scale or the ranking? Split-half recalibration

Fit a monotone (isotonic) map from model p to human rate on half the items, apply
to the other half, 20 seeds x 2 folds, all figures held-out.

| Arm | Brier before | Brier after | ECE after | AUC after | Base rate Brier |
|---|---|---|---|---|---|
| Jev, full 4,554 | 0.098 | **0.017** | 0.008 | 0.857 | 0.035 |
| Laya, full 4,554 | 0.023 | 0.022 | 0.008 | 0.797 | 0.035 |
| Jev, the 100 | 0.104 | 0.019 | 0.045 | 0.822 | 0.029 |
| Laya, the 100 | 0.021 | 0.023 | 0.043 | 0.827 | 0.029 |
| Sonnet, the 100 | 0.037 | 0.023 | 0.044 | 0.773 | 0.029 |

This is the study's sharpest result. Laya barely moves, because there was
nothing wrong with its scale; on the 100 the fit costs it slightly, having
learned noise from 50 items. Jev moves from worst to best, and **recalibrated
Jev (0.017) beats recalibrated Laya (0.022)**.

Scale is repairable. Ranking is not repairable at all: no monotone map can
reorder items. So the model with the better ranking and the broken scale is the
better buy, provided you actually do the repair. The danger is that the broken
scale is invisible if you never measure it, and 0.85 looks like a fine number to
threshold at.

### How many labelled examples the repair needs

`recal_curve.py` fits the isotonic map on n random items and scores the rest, 40
seeds per size. Everything below is held out of the fit (Jev, n = 4,554; raw
Brier 0.0979, constant base rate 0.0354).

| fit items | Brier | ECE | Brier cut vs raw | vs base rate |
|---|---|---|---|---|
| 25 | 0.0222 | 0.0440 | 77% | 37% |
| 50 | 0.0199 | 0.0299 | 80% | 44% |
| 100 | 0.0186 | 0.0218 | 81% | 47% |
| 150 | 0.0182 | 0.0174 | 81% | 49% |
| 250 | 0.0178 | 0.0142 | 82% | 50% |
| 500 | 0.0176 | 0.0112 | 82% | 50% |
| 1,000 | 0.0174 | 0.0095 | 82% | 51% |
| 2,000 | 0.0171 | 0.0084 | 82% | 52% |

The curve is flat past about 100 items. 150 gets within 6% of what 2,000 gets,
and 25 already removes three quarters of the raw error. Brier saturates earlier
than ECE, so fit more if you care about the probability reading true across the
whole range rather than about accuracy.

Caveat: this is 150 items drawn from the same 4,554. A labelled set gathered
some other way, or drifting away from the items it was fitted on, will not do as
well.

### Does the fan-out change the number?

Paired: the same 300 items asked both ways, one question per call versus nine
nouls plus a score in a single call.

| | Brier | ECE | AUC |
|---|---|---|---|
| one question per call | 0.0991 | 0.2504 | 0.8776 |
| fan-out | 0.0991 | 0.2506 | 0.8771 |

Per item, not just in aggregate: 105 of 300 answers came back identical, mean
absolute move 0.0111, median 0.0100, max 0.0600, none moved more than 0.10.
Asking Jev the *same* question three times moves it 0.0115 on average, so
batching perturbs the answer no more than rerunning it does.

Caveat for a pass/fail check: 5 of the 300 crossed the 0.5 line anyway, 1.7%.
Batching is free in accuracy terms, not bit-identical.

This matters beyond this study: "several questions about one state in a single
call" is the capability that distinguishes a decision operation type from plain
text classification. On this evidence the win is latency and cost, not better
answers.

### Run-to-run stability

| Arm | Items x runs | Identical answers | mean abs change in p | max |
|---|---|---|---|---|
| Jev | 100 x 3 | 94 of 300 pairs | 0.011 | 0.050 |
| Sonnet | 30 x 2 | 13 of 30 | 0.034 | 0.120 |

Neither is deterministic. Jev moves about a third as much.

### Per region (weak)

Region-specific questions ("would a typical reader living in the Sinosphere find
this offensive?") barely move with the region. Mean Jev p per region ranges 0.49
to 0.56 while mean human rates range 0.27 to 0.41; ordering the eight regions by
model versus by humans gives Spearman 0.357. Caveat: about three raters per
region per item, so item-level regional truth is noisy, though the aggregate over
4,500 items is not.

### Severity

Jev's 0-4 score correlates with the mean raw rating at Spearman 0.737 but sits
high: mean 1.82 versus 1.19.

### By item category

| Category | n | Jev AUC | Jev ECE |
|---|---|---|---|
| moral | 462 | 0.929 | 0.182 |
| random | 1,713 | 0.850 | 0.222 |
| social-group | 2,379 | 0.804 | 0.288 |

Hardest where humans disagree most: messages about social groups.

## The second arm: Laya, and what "calibrated" actually means

[Laya](https://github.com/NandhaKishorM/laya) (Apache-2.0) is an open-weights
System 1 engine: ModernBERT-large 421M or mmBERT-base 322M, non-autoregressive,
with the same typed question shape as System One (`noul` / `choice` / `score`,
`answers[key]["noul"]` is a probability). `pip install laya`, no key, runs on a
laptop CPU at about 0.85 s per question here and 33 ms on a T4. It was published
before Jev. Its own README concedes the scale problem in the same terms this
study measured on Jev:

> Both checkpoints are over-confident as shipped. Refitting one temperature per
> (question type, option count) on held-out data moves mean ECE 0.466 -> 0.081

On D3code it is the best-calibrated arm by a wide margin and needs no repair.
Its calibration curve is nearly the diagonal:

| Laya p bin | n | mean p | mean human rate | gap |
|---|---|---|---|---|
| 0.0-0.1 | 155 | 0.08 | 0.09 | -0.01 |
| 0.1-0.2 | 775 | 0.16 | 0.18 | -0.03 |
| 0.2-0.3 | 1,095 | 0.25 | 0.29 | -0.04 |
| 0.3-0.4 | 1,068 | 0.35 | 0.36 | -0.01 |
| 0.4-0.5 | 740 | 0.45 | 0.43 | +0.02 |
| 0.5-0.6 | 456 | 0.55 | 0.48 | +0.06 |
| 0.6-0.7 | 207 | 0.64 | 0.54 | +0.10 |
| 0.7-0.8 | 48 | 0.74 | 0.60 | +0.14 |
| 0.8-0.9 | 10 | 0.82 | 0.62 | +0.20 |

Compare the Jev table above, where the same bins run +0.31, +0.37, +0.39. Laya
is also cautious: only 58 of 4,554 items clear p = 0.7 and none clears 0.9,
while human agreement runs all the way to 1.0 (19 items sit at 0.875 or above).

### Then we asked it our own questions, and it fell over

> **The numbers in this section come from a separate experiment that is not in
> this repository**, and cannot be reproduced from `results-compact.jsonl`. They
> are reported here because they are the reason the conclusions above are
> hedged. The probe runs against the `semantic_yes` rubric check in
> [drupal/ai_best_practices](https://www.drupal.org/project/ai_best_practices),
> its Drupal-specific rubrics and its fixtures, none of which belong in a study
> of D3code. Everything else in this README is reproducible here.

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

Jev is still clearly better on our questions. Laya is no longer useless on them,
and the original "soft yes to everything" reading was an artifact.

### The finding

Two things, and the second one nearly ate the first.

**1. Rank and scale are different properties, and only one is repairable.** On
D3code Jev ranks better and is badly scaled; Laya is well scaled and ranks
worse. A monotone map fixes a scale from about 150 labelled examples and cannot
reorder anything, so recalibrated Jev (Brier 0.017) beats recalibrated Laya
(0.022). A published ECE, including every one in this README, licenses nothing
about your data: measure on your own items before you pick a threshold.

**2. A silent provider mismatch looks exactly like a bad model.** The rubric
check emits Jev's documented shape. Laya accepts the same call, and
something about the extra key collapses its answers into a 0.19-wide band that
reads as "this model has no idea". No error, no warning. It took a direct
challenge to go and check, and a second one to establish that the key is not
simply dropped. Anyone benchmarking two providers through one harness is one
undocumented key away from publishing a verdict about the wrong thing.

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

## What this means for `semantic_yes`

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

## Caveats

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

## Tried and dropped: Needle (Cactus Compute)

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

## Reproduce

### Every table above, from the shipped results

No keys, no downloads, no pip install. Each command prints the table it is
named after.

```bash
R=results-compact.jsonl

# "Overall, full dataset", and the calibration curves
python3 metrics.py $R --arm jev-full  --label jev
python3 metrics.py $R --arm laya-full --label laya

# "Head to head on the same 100 items"
python3 metrics.py $R --arm jev-100 --label jev
python3 metrics.py $R --arm sonnet-100 --label sonnet
python3 metrics.py $R --arm laya-100 --label laya

# "Is it the scale or the ranking?"
python3 recal.py $R --arm jev-full
python3 recal.py $R --arm laya-full

# "How many labelled examples the repair needs"
python3 recal_curve.py $R --arm jev-full

# the confidence intervals, and the paired between-arm differences
python3 intervals.py $R --arm jev-full --vs laya-full --boots 400
python3 intervals.py $R --arm jev-100 --vs sonnet-100 --boots 2000

# "Does the fan-out change the number?", including the rerun-noise baseline
python3 fanout_paired.py $R $R --arm jev-300 --single-arm jev-single \
    --repeat $R $R $R --repeat-arm jev-100 jev-100-rep2 jev-100-rep3
```

Scoring the combined file without `--arm` is refused rather than answered, since
the rows of ten arms share item ids and the answer would silently be one
arbitrary arm's.

### From scratch, against the models

Download the D3code CSVs into a directory and point `$D` at it. This costs money
for the Jev and Sonnet arms and takes about 80 minutes for the Laya arm on CPU.

```bash
export D=~/d3code            # holds d3-items.csv, d3-raters.csv, d3-ratings.csv

# Jev, full set. --sample-out records the item order every other arm reuses.
python3 jev_arm.py --data $D --n 4590 --seed 1 \
    --out $D/jev_full.jsonl --sample-out $D/sample_full.json --workers 8

# the 100-item subset the head-to-head uses, cut from that same order
python3 -c "import json,sys; ids=json.load(open(sys.argv[1])); json.dump(ids[:100], open(sys.argv[2],'w'))" \
    $D/sample_full.json $D/sample100.json

python3 llm_judge_arm.py --data $D --sample-in $D/sample100.json \
    --out $D/sonnet100.jsonl --model sonnet --limit 100

pip install laya   # no key; about 5.8 GB of venv, it pulls CUDA in without a GPU
python3 laya_arm.py --data $D --sample-in $D/sample_full.json \
    --out $D/laya_full.jsonl --checkpoint router --overall-only
python3 laya_arm.py --data $D --sample-in $D/sample100.json \
    --out $D/laya100.jsonl --checkpoint router

# the same scoring, on single-arm files, where --arm is not needed
python3 metrics.py $D/jev_full.jsonl --label jev
python3 recal.py $D/jev_full.jsonl
```

Needs `TYPESAFE_API_KEY` (or `~/.config/typesafe/api.key`) for the Jev arm and a
logged-in `claude` CLI for the judge arm. The Laya arm needs neither.

Run one model at a time: two loaded checkpoints plus the scoring ran a 15 GB box
out of memory during this study.

Fresh arm files contain the D3code item texts. `.gitignore` keeps `*.jsonl` out
of commits for that reason, with `results-compact.jsonl` excepted.

## Licence and attribution

The code here is GPL-2.0-or-later. Every source file carries an SPDX header;
[LICENSE](LICENSE) is the GPL version 2 text, and "or later" is the grant those
headers make. `systemone.py` is derived from `evals/semantic.py` in
[drupal/ai_best_practices](https://www.drupal.org/project/ai_best_practices),
same licence, with the rubric-facing half removed.

The [D3code dataset](https://github.com/google-research-datasets/D3code), linked
under "Ground truth", is by Google Research and licensed CC-BY 4.0. Its item
texts are deliberately not republished here: `results-compact.jsonl` carries
only item ids, human agreement rates and model outputs. Re-fetch the texts from
D3code by `item_id` if you need them.

Where this README says "150,000 human ratings" it means D3code's published total
of 150,702. The rows this study can actually use, after dropping the ones marked
unavailable, number 144,730.
