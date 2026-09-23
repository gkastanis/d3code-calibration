# Does that probability mean anything?

A model says 0.85. Does that mean yes about 85% of the time, or only that this
item ranks above one scored 0.84?

On this dataset it meant neither. When TypeSafe's Jev reported about 0.85, the
mean human agreement rate in that bin was 0.45. A threshold of 0.5 therefore did
not mean "most people agree". The ordering was good and the scale was wrong.

That is the repairable kind of wrong, and the repair is cheap. A held-out
isotonic recalibration took Jev's Brier score from 0.098 to 0.017. Twenty-five
labelled examples removed 77% of the raw error, and 150 came within 6% of what
2,000 gave. What no recalibration can repair is the ordering, because a monotone
map never swaps two items. So on these 4,554 items Jev, which ranked better than
the open-weights Laya but was badly scaled, ends up ahead after the repair: Laya
started closer, at 0.023, and the same fit moved it only to 0.022.

All of that describes this dataset. It says nothing about either model on your
task, which is why the tools are here alongside the study. Give `recal.py` and
`recal_curve.py` a list of pairs, what your model said and what turned out to be
true, and they will tell you whether your problem is the scale or the ordering,
and roughly how many labels the repair would take. Neither script knows anything
about Jev, Laya, D3code or offensiveness.

## What to do with a probability in an application

Use the model's number to rank candidates only after checking that it orders your own labelled items usefully. Choose a pass/fail threshold from those items. If the number must mean "about this fraction of cases are yes", fit a calibration map on separate labelled items and check it on held-out items. A published calibration score, including one in this README, does not set a threshold for a new task.

For our `semantic_yes` rubric, the practical observations are these:

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

## Run the shipped checks

Python 3.10 or newer. The scoring path uses the standard library. The included results need no API key, model download or pip install:

```bash
python3 metrics.py  results-compact.jsonl --arm jev-full  --label jev
python3 metrics.py  results-compact.jsonl --arm laya-full --label laya
python3 recal.py    results-compact.jsonl --arm jev-full
python3 intervals.py results-compact.jsonl --arm jev-full --vs laya-full
```

`results-compact.jsonl` contains every row of every arm, identified by an `arm` field, with the item texts removed. The complete commands are under [Reproduce](#reproduce). Running models afresh requires `pip install laya` for the local Laya arm, a TypeSafe API key for Jev, the `claude` CLI for Sonnet, and the original D3code download for item texts.

## How to read the measures

A `noul` is a typed yes/no question whose answer is a probability. Here the target is the fraction of human raters who answered yes for each item. **Brier** is average squared error between that fraction and the model probability; lower is better. **ECE** groups probabilities into bins and averages the gaps between each bin's mean prediction and mean observed rate; lower is better. The constant base-rate predictor has ECE 0.000 by construction, even though it cannot distinguish items.

**Spearman** measures how well two sets of values rank the same items. **AUC** measures how often a positive item ranks above a negative item, here using the crowd-majority label. Higher is better for both. Neither says that a probability such as 0.8 means 80%.

A **paired bootstrap** repeatedly resamples the same item ids for both models. Its displayed intervals show the uncertainty of their difference on this sample. **Isotonic recalibration** fits a non-decreasing map from reported probability to human rate. It can change the scale without reversing the model's order. The recalibration results below score items held out from each fit.

## Study design

Jev returns a probability for a yes/no question rather than text, with calibration among its advertised properties. Our eval rubric thresholds that number. Our own repository had only five traces and eight labels, so we used D3code to ask whether a reported probability tracks human agreement.

### Human ratings

[D3code](https://github.com/google-research-datasets/D3code) (Google Research,
CC-BY 4.0): 4,590 short online messages from the Jigsaw corpus, each rated for
offensiveness on a 0-4 scale by about 24 people, balanced across eight
geo-cultural regions, 4,309 raters, 150,702 ratings. A rating of 2 or more counts
as "offensive". So every item has a human agreement rate: the fraction of raters
who called it offensive, overall and per region. That fraction is the target a
calibrated probability should track.

34 item ids appear twice in the items file; metrics keep the first scored row per
id, leaving 4,554 items.

### Model arms and protocols

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

## Main result: recalibration changes the comparison

The fit was a monotone isotonic map from model probability to human rate, trained on half the items and applied to the other half. Results use 20 seeds x 2 folds; every figure in this table is held out.

| Arm | Brier before | Brier after | ECE after | AUC after | Base rate Brier |
|---|---|---|---|---|---|
| Jev, full 4,554 | 0.098 | **0.017** | 0.008 | 0.857 | 0.035 |
| Laya, full 4,554 | 0.023 | 0.022 | 0.008 | 0.797 | 0.035 |
| Jev, the 100 | 0.104 | 0.019 | 0.045 | 0.822 | 0.029 |
| Laya, the 100 | 0.021 | 0.023 | 0.043 | 0.827 | 0.029 |
| Sonnet, the 100 | 0.037 | 0.023 | 0.044 | 0.773 | 0.029 |

Laya's full-set Brier score barely changes because its raw scale is already close to the human rate here. On the 100-item subset, the fit slightly worsens it after learning from 50 items. Jev moves from the worst raw Brier score to the best recalibrated one: 0.017 against Laya's 0.022 on the full set. That result depends on actually fitting a map to relevant labelled data. A monotone map cannot reorder items.

### Raw probabilities on the full dataset (n = 4,554, both models on every item)

| Metric | Jev raw | Laya raw | Base rate |
|---|---|---|---|
| Brier vs human rate (lower is better) | 0.098 | **0.023** | 0.035 |
| Calibration error (ECE, 10 bins) | 0.251 | **0.033** | 0.000 |
| Spearman(p, human rate) | **0.710** | 0.622 | n/a |
| AUC vs majority label | **0.858** | 0.798 | 0.500 |
| Accuracy at p >= 0.5 | 0.557 | **0.797** | 0.784 |

The two split cleanly: **Jev ranks better, Laya is scaled better.** Jev is the
only arm whose raw probability loses to a constant.

The displayed paired intervals for all five differences exclude zero. Paired bootstrap, 400
resamples of the 4,554 shared items, scoring both arms on the same resample
(`intervals.py --arm jev-full --vs laya-full`):

| Metric | Jev 95% CI | Laya 95% CI | Jev minus Laya | Excludes zero |
|---|---|---|---|---|
| Brier | 0.095 to 0.101 | 0.022 to 0.024 | +0.074 (+0.071, +0.077) | yes |
| ECE | 0.245 to 0.257 | 0.029 to 0.037 | +0.219 (+0.212, +0.226) | yes |
| Spearman | 0.695 to 0.725 | 0.602 to 0.641 | +0.088 (+0.069, +0.108) | yes |
| AUC | 0.844 to 0.870 | 0.784 to 0.812 | +0.061 (+0.046, +0.076) | yes |
| Accuracy at 0.5 | 0.544 to 0.571 | 0.786 to 0.809 | -0.240 (-0.260, -0.223) | yes |

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

In these bins, the predictions below 0.2 are close to the mean human rates. Above 0.5 the gaps are large. When Jev says 0.85,
45% of people agreed. It ranks well and reads strict: the number behaves like
one severe rater, not like the average of 24.

### How much labelled data did the repair need here?

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

### The 100-item comparison supports calibration, not ranking

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

**The Spearman and AUC differences on these 100 items do not distinguish the three models.** Paired bootstrap, 2,000 resamples
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

The narrower calibration claims and the uncertain ranking claims need to stay separate.

## Supporting checks

### Fan-out changes little on the paired Jev sample

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

### Repeated calls vary

| Arm | Items x runs | Identical answers | mean abs change in p | max |
|---|---|---|---|---|
| Jev | 100 x 3 | 94 of 300 pairs | 0.011 | 0.050 |
| Sonnet | 30 x 2 | 13 of 30 | 0.034 | 0.120 |

Neither is deterministic. Jev moves about a third as much.

### Region-specific answers vary little

Region-specific questions ("would a typical reader living in the Sinosphere find
this offensive?") barely move with the region. Mean Jev p per region ranges 0.49
to 0.56 while mean human rates range 0.27 to 0.41; ordering the eight regions by
model versus by humans gives Spearman 0.357. Caveat: about three raters per
region per item, so item-level regional truth is noisy, though the aggregate over
4,500 items is not.

### Severity scores sit high

Jev's 0-4 score correlates with the mean raw rating at Spearman 0.737 but sits
high: mean 1.82 versus 1.19.

### Social-group items are harder

| Category | n | Jev AUC | Jev ECE |
|---|---|---|---|
| moral | 462 | 0.929 | 0.182 |
| random | 1,713 | 0.850 | 0.222 |
| social-group | 2,379 | 0.804 | 0.288 |

Hardest where humans disagree most: messages about social groups.

## Laya is better calibrated on D3code

[Laya](https://github.com/NandhaKishorM/laya) (Apache-2.0) is an open-weights
System 1 engine: ModernBERT-large 421M or mmBERT-base 322M, non-autoregressive,
with the same typed question shape as System One (`noul` / `choice` / `score`,
`answers[key]["noul"]` is a probability). `pip install laya`, no key, runs on a
laptop CPU at about 0.85 s per question here and 33 ms on a T4. It was published
before Jev. Its own README concedes the scale problem in the same terms this
study measured on Jev:

> Both checkpoints are over-confident as shipped. Refitting one temperature per
> (question type, option count) on held-out data moves mean ECE 0.466 -> 0.081

On D3code it has the lowest raw ECE of the model arms and needs little repair.

Its calibration curve is close to the diagonal:

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

The same bins in the Jev table run +0.31, +0.37 and +0.39. Laya is also
cautious: only 58 of 4,554 items clear p = 0.7 and none clears 0.9, while human
agreement runs all the way to 1.0 (19 items sit at 0.875 or above).

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

## Reproduce

### D3code results from the shipped file

No keys, no downloads, no pip install. These commands reproduce the D3code result tables and checks named below. The separate Drupal probe above is not in the shipped file.

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
under "Human ratings", is by Google Research and licensed CC-BY 4.0. Its item
texts are deliberately not republished here: `results-compact.jsonl` carries
only item ids, human agreement rates and model outputs. Re-fetch the texts from
D3code by `item_id` if you need them.

Where this README says "150,000 human ratings" it means D3code's published total
of 150,702. The rows this study can actually use, after dropping the ones marked
unavailable, number 144,730.
