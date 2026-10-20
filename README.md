# Does that probability mean anything?

Some AI models answer a yes/no question with a number instead of words. Not
"yes", but `0.85`. The number is supposed to mean "how sure I am".

I checked whether it does.

**The finding, in five sentences.**

1. I took 4,554 short online messages that about 24 people each had judged, so
   for every message you know what fraction of real people found it offensive.
2. I asked two of these models the same question about every message.
3. When TypeSafe's Jev answered `0.85`, about **45%** of people had actually
   agreed. The number reads far more certain than it is.
4. But it put the messages in roughly the **right order**. Higher scores
   generally separated the messages most people called offensive from the
   ones most did not.
5. On this data the **ordering held up far better than the number**, and the
   number can be corrected: about **150 examples labelled here** were enough,
   25 got most of the way. Ordering is not automatically trustworthy either,
   which is the next section.

That is the whole study. Everything in [docs/](docs/) is me showing the working.

## What this means if you are wiring one of these into something

**Do not ship `0.5` as a threshold as though it means "more likely than not".**
On this data, the point where most people actually agreed sat near `0.9`, not
`0.5`. On this dataset, items scored around 0.5 had an average agreement rate
of roughly one in four, so a site owner who types 0.5 into a settings form is
not getting a coin flip.

**Use the number to sort things, not to decide things,** until you have checked
it against examples from your own task.

**If you need the number itself to be meaningful**, label some of your own cases
and fit a correction. On this dataset around 150 corrected most of the scale
error and 25 got most of the way, but that is a measurement here, not a recipe
for your task. `recal_curve.py` gives you the curve for your own data.

**Calibration is not guaranteed to transfer.** A model that is well calibrated
on someone else's benchmark can be useless on your questions. That happened to us here,
and it is written up in [limits.md](docs/limits.md).

## Check it yourself

Python 3.10 or newer, no API key, no downloads, no `pip install`:

```bash
git clone https://github.com/gkastanis/d3code-calibration
cd d3code-calibration

python3 metrics.py results-compact.jsonl --arm jev-full  --label jev
python3 recal.py   results-compact.jsonl --arm jev-full
```

Every script prints its tables and then says, in words, what they mean. The end
of the first one reads:

```
What this says about jev-full, in plain words:
  When it answered about 0.85, the real answer was yes 45% of the time (791 items).
  It sounds more certain than it is.
  Ordering: take one item that really was a yes and one that really was a no. It
  scores the yes higher 86% of the time. That is a strong ordering.
  Its raw numbers are WORSE than ignoring the model and always answering 0.34
  (error 0.098 against 0.035).
  Verdict: use it to RANK, not to threshold. The ordering carries signal and the
  number does not mean what it says. Run recal.py to see how much a correction fixes.
```

Those sentences are computed from your data, not written in advance, so they
follow the numbers when you point the scripts at something else.

The two scripts worth stealing know nothing about this study:

- **`recal.py`** answers "is my problem the scale or the ordering?" A
  calibration can fix the scale. It cannot fix bad ordering, though a
  different model, prompt or task framing might.
- **`recal_curve.py`** answers "how many labelled examples would fixing it
  take?"
- **`transfer.py`** answers "can I reuse a correction somewhere else?" It
  fits the same correction as `recal.py` and tests it on new kinds of content
  and on another model. On another model it made the numbers worse.

Give either one a list of pairs, what your model said and what turned out to be
true, and point it at your own data.

## The longer version

- **[docs/results.md](docs/results.md)**: every measurement, with confidence
  intervals, and the comparison against Claude Sonnet and the open-weights Laya.
- **[docs/method.md](docs/method.md)**: the dataset, what each model was asked,
  what Brier and ECE and the rest actually mean, and how to reproduce every
  table.
- **[docs/limits.md](docs/limits.md)**: what this does not show, two claims an
  earlier draft of mine got wrong, and one model that was tried and dropped.

## Other calibration results

Other reports show that calibration varies across tasks and evaluation setups.
The ones below were read in full; the quotations are verbatim.

**[Laya](https://github.com/NandhaKishorM/laya)**, one of the two models measured
here, says it about itself in its own README:

> Both checkpoints are over-confident as shipped. Refitting one temperature per
> (question type, option count) on held-out data moves mean ECE 0.466 -> 0.081

**[AnyJev](https://github.com/nokia-applied-research/AnyJev)** (Nokia Applied
Research and Tencent Hunyuan, Apache-2.0) turns any open LLM into a decision
model by reading the probability out of the next-token distribution. Its README:

> Raw logits change their answer when you reorder the options, and their
> confidence cannot be trusted; AnyJev fixes the first with zero labels and the
> second with a few hundred.

It reports calibration error of 0.240 raw, falling to 0.095 with 100 to 500
labels per question.

Beside this study: Jev's raw calibration error here was 0.251, and the correction
needed around 150 labels before the curve flattened. These three reports (Laya,
AnyJev, this study) describe calibration improvements using labelled data, with
different models, tasks and corrections.

Those numbers are not directly comparable. Different models, different tasks,
and different corrections: AnyJev scales a temperature, this study fits an
isotonic map. Read them as three arrows pointing the same way, not as a league
table.

Five people also benchmarked Jev's calibration in its first two weeks, each
against one gold label per item, and the picture is task-dependent:
[Mike Moore](https://github.com/themsquared/jev-benchmark) (60 tool-call risk
cases, ECE 0.05 to 0.07, "on this task set, the calibration claim holds"),
[Dhruv Mehra](https://github.com/dhruvmehra/jevbench) (500 items each on
SST-2, AG News, Banking77: ECE 0.026, 0.112, 0.125),
[instax-dutta](https://github.com/instax-dutta/sysone-bench) (310 items, ECE
0.03 to 0.06), [AbdelStark](https://github.com/AbdelStark/jev-benchmarks)
(300 items, "substantially worse calibrated" on DAIR Emotion),
[Pavel Ravvich](https://github.com/PavelRavvich/jev-bench) (1,000 items, "On
Banking77 Jev's ECE is the worst of the three on the shared subset").

Two more address related questions and reach different practical conclusions.
[Alex Molas](https://www.alexmolas.com/2026/09/23/jev-cant-be-calibrated.html)
argues that calibration need not transfer between data distributions, and
cites reported failures without presenting a new benchmark: "A model can be
calibrated on TypeSafe's data and still be miscalibrated on yours", so "treat
Jev's outputs as good scores (they rank examples well) rather than good
probabilities" and refit on a few hundred labelled examples.
[Leonard Grazian](https://leonardgrazian.com/blog/jev-calibration/) responds
with results on two datasets. Like this study, he evaluates against annotator
vote shares rather than a single gold label, although the task and annotator
population differ: after prompt tuning on labelled examples, ECE 0.025 against
100-rater vote shares on 612 held-out ChaosNLI stories, and 0.027 against
binary labels on 3,066 WiC examples. He reports no untuned calibration
baseline. His warning, "Without tuning, the Jev probability will have no
bearing on your ground truth", is about aligning the question with the labels;
his experiment does not measure how much tuning changed calibration.

Side by side: Grazian reports low calibration error after prompt tuning. This
study reports high error with its original prompt (items scored around 0.85
averaged about 45% human agreement) and low held-out error after
recalibration (an isotonic map fitted on half the items took ECE from 0.251 to
0.008 on the other half). Without an untuned baseline from Grazian, nobody can
tell whether tuning explains the difference. What both show is that a
threshold should be checked against the intended task and population before
anyone relies on it; neither shows that every untuned prompt is miscalibrated,
or that every threshold after correction is safe.

What was built differs too. AnyJev is a model-level approach and needs a model
whose internals you can read. This repository provides the calibration check
and a score recalibration from model outputs and labels, and it works on
anything with an API, including closed models like Jev.

## How this was made

The measurements are real: this study's results are reproducible from the
shipped results file with the commands in [method.md](docs/method.md).
External results are attributed to their sources and were not rerun here.

The work was done with AI assistance and it would be silly to pretend otherwise.
I set the questions, chose the dataset, made the calls about what was worth
measuring, and twice caught the assistant asserting things it had not checked
(both are written up in [limits.md](docs/limits.md), because catching them is
the point). Claude wrote most of the code and prose, OpenAI's Codex did a
portability pass and an independent readability review, and a separate review
agent went through the repository looking for exactly the kind of error that
would embarrass me here.

Judge it by whether it reproduces. That is why it is all here.

## Licence and attribution

The code is GPL-2.0-or-later. Every source file carries an SPDX header;
[LICENSE](LICENSE) is the GPL version 2 text, and "or later" is the grant those
headers make. `systemone.py` is derived from `evals/semantic.py` in
[drupal/ai_best_practices](https://www.drupal.org/project/ai_best_practices),
same licence, with the rubric-facing half removed.

The [D3code dataset](https://github.com/google-research-datasets/D3code) is by
Google Research, licensed CC-BY 4.0. Its item texts are deliberately not
republished here: `results-compact.jsonl` carries only item ids, human agreement
rates and model outputs. Re-fetch the texts from D3code by `item_id` if you need
them. They are offensive by construction, which is the reason.

Where this repository says "150,000 human ratings" it means D3code's published
total of 150,702. The rows this study can actually use, after dropping the ones
marked unavailable, number 144,730.
