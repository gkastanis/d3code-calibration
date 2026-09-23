# Results

Every measurement, with confidence intervals. The short version is in the
[README](../README.md); this is the evidence behind it.

[Back to the README](../README.md)

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
