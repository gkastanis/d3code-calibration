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
4. But it put the messages in roughly the **right order**. The ones it scored
   highest really were the ones people found worst.
5. The order is the part you can trust. The number can be corrected, and it
   takes surprisingly little: about **150 examples you have labelled yourself**.

That is the whole study. Everything in [docs/](docs/) is me showing the working.

## What this means if you are wiring one of these into something

**Do not ship `0.5` as a threshold as though it means "more likely than not".**
On this data, the point where most people actually agreed sat near `0.9`, not
`0.5`. A site owner who types 0.5 into a settings form is not getting a coin
flip, they are getting roughly one in four.

**Use the number to sort things, not to decide things,** until you have checked
it against examples from your own task.

**If you need the number itself to be meaningful**, label 150 or so of your own
cases and fit a correction. 25 got most of the way. The tools here do it.

**Calibration does not travel.** A model that is well calibrated on someone
else's benchmark can be useless on your questions. That happened to us here,
and it is written up in [limits.md](docs/limits.md).

## Check it yourself

Python 3.10 or newer, no API key, no downloads, no `pip install`:

```bash
git clone https://github.com/gkastanis/d3code-calibration
cd d3code-calibration

python3 metrics.py results-compact.jsonl --arm jev-full  --label jev
python3 recal.py   results-compact.jsonl --arm jev-full
```

The first prints how far the raw numbers were from reality. The second shows how
much of that a correction fixes.

The two scripts worth stealing know nothing about this study:

- **`recal.py`** answers "is my problem the scale or the ordering?" Scale is
  fixable. Ordering is not.
- **`recal_curve.py`** answers "how many labelled examples would fixing it
  take?"

Give either one a list of pairs, what your model said and what turned out to be
true, and point it at your own data.

## The longer version

- **[docs/results.md](docs/results.md)** — every measurement, with confidence
  intervals, and the comparison against Claude Sonnet and the open-weights Laya.
- **[docs/method.md](docs/method.md)** — the dataset, what each model was asked,
  what Brier and ECE and the rest actually mean, and how to reproduce every
  table.
- **[docs/limits.md](docs/limits.md)** — what this does not show, two claims an
  earlier draft of mine got wrong, and one model that was tried and dropped.

## How this was made

The measurements are real: every number here comes from a run that is
reproducible from the shipped results file, and the commands are in
[method.md](docs/method.md).

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
