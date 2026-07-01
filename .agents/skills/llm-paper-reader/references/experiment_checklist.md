# Experiment Checklist

Use this checklist when reading experiments, baselines, ablations, benchmarks, and implementation details.

## Experimental Setup

- Dataset names and splits
- Training, validation, and test settings
- Prompting or decoding settings
- Model sizes and checkpoints
- Fine-tuning, pretraining, or inference-only setup
- Hardware or cost details if stated

## Baselines

- Baseline names
- Whether baselines are prior work, model variants, or internal ablations
- The baseline's minimum operational flow needed by the default reader
- The exact component, objective, data, or inference step that differs from the paper's method
- Whether comparisons are fair according to the paper's setup
- Missing baselines that affect interpretation

Do not assume a baseline name explains the comparison. When the baseline is central, give the
reader the shortest grounded explanation needed to understand what changed and why the comparison
tests the paper's claim.

## Metrics

- Metric names
- What each metric measures
- Whether higher or lower is better
- A small intuitive example of what would make the metric improve or worsen when the metric is not
  obvious from basic deep-learning knowledge
- Whether the metric directly supports the claimed contribution
- Any human evaluation protocol

## Results

For each important result, record:

- table or figure anchor
- dataset
- metric
- best model or method
- absolute score
- relative improvement if stated
- author's interpretation
- what the result actually supports
- why the observed direction would follow from the proposed mechanism, if the evidence supports
  that interpretation
- whether the original table should be cropped and embedded in the report

## Ablations

For each ablation, identify:

- removed or changed component
- expected effect
- observed effect
- which claim it validates
- whether the ablation isolates one factor cleanly
- whether the original ablation table or curve should be cropped and embedded

## Table Use

Use original result tables when they are central to the paper's argument. Crop table images so they contain only the table body and necessary headers/legend, not surrounding page text.

For each embedded table, explain:

- the claim the table is meant to support
- which rows/columns matter
- the strongest numeric comparison
- what the table does not prove
- whether any fairness caveat, missing baseline, or setting mismatch affects interpretation

## Reliability Questions

- Are results averaged across runs?
- Are statistical tests or confidence intervals provided?
- Are prompts, hyperparameters, data filters, or code released?
- Are negative results or failure cases shown?
- Are there signs that the method is benchmark-specific?
- Does the paper distinguish correlation from causal evidence?
- Which negative results or uncovered settings are explicitly acknowledged as limitations?
- Which future experiments, datasets, model changes, or evaluations do the authors propose?
