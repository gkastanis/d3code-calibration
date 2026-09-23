# Method

How the study was built: the dataset, what each model was asked, what the
measures mean, and the commands that reproduce every table.

[Back to the README](../README.md)

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

## How to read the measures

A `noul` is a typed yes/no question whose answer is a probability. Here the target is the fraction of human raters who answered yes for each item. **Brier** is average squared error between that fraction and the model probability; lower is better. **ECE** groups probabilities into bins and averages the gaps between each bin's mean prediction and mean observed rate; lower is better. The constant base-rate predictor has ECE 0.000 by construction, even though it cannot distinguish items.

**Spearman** measures how well two sets of values rank the same items. **AUC** measures how often a positive item ranks above a negative item, here using the crowd-majority label. Higher is better for both. Neither says that a probability such as 0.8 means 80%.

A **paired bootstrap** repeatedly resamples the same item ids for both models. Its displayed intervals show the uncertainty of their difference on this sample. **Isotonic recalibration** fits a non-decreasing map from reported probability to human rate. It can change the scale without reversing the model's order. The recalibration results below score items held out from each fit.

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
