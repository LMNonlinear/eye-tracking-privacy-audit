# Group Privacy Audit for Eye-Tracking Identification

This repository provides a score-table audit for comparing identification risk between two groups across privacy-protection conditions. It calculates equal-fold group risks, residual differences, changes from baseline, pointwise confidence intervals and Holm-adjusted comparisons. It also records descriptive diagnostics and input provenance.

The repository contains **synthetic examples only**. It does not contain eye-tracking recordings, participant data, trained model weights or the paper's individual-level scores.

## Run the synthetic example

Use Python 3.11 or later, then install the dependencies and run from the repository root:

```bash
python -m pip install -r requirements.txt
python -m scripts.run_robust_privacy_audit --scores examples/privacy_pipeline_scores.csv --plan configs/privacy_pipeline_blocked_example.json --output results/example_audit
```

The output directory must not already exist. The command writes `results/example_audit/report.json` for machine processing and `results/example_audit/report.pdf` for reading and sharing. An example JSON is included as `examples/ROBUST_AUDIT_SYNTHETIC_REPORT.json`. Its residual difference is zero; the baseline-relative change has zero sampling variance, so the software withholds that formal decision. These synthetic values are not results from the study.

To produce a Chinese PDF, add `--report-language zh` to the command. A suitable system TrueType Chinese font is required. If a font is unavailable or lacks a character in the report, use `--report-font` with a Unicode `.ttf` or `.ttc` font path. The English report is the default; its bundled font supports common Latin characters. Both report languages embed their selected font. Reports are written locally; the tool does not upload scores or results.

For a more detailed artificial example with 200 simulated participants and three conditions, generate a fresh fixture and audit it:

```bash
python examples/generate_illustrative_scores.py --output results/illustrative_inputs
python -m scripts.run_robust_privacy_audit --scores results/illustrative_inputs/synthetic_scores.csv --plan results/illustrative_inputs/plan.json --output results/illustrative_audit --report-language zh
```

The fixture uses a fixed random seed and is solely for demonstrating the report. It is neither a study dataset nor a calibration experiment.

To render an existing JSON without recalculating the analysis, choose a new PDF path:

```bash
python -m scripts.render_audit_report --input results/example_audit/report.json --output results/example_audit/report_zh.pdf --report-language zh
```

Existing output files are never overwritten. If PDF generation fails, the command reports the error and preserves any `report.json` already written; render that JSON again after resolving the font or output issue.

## Input and comparison plan

The CSV requires `subject_id,fold,group,evaluator,condition,replicate,rank1_ir`. Scores are finite percentages from 0 to 100. The plan specifies one ordered group pair, a baseline, declared conditions and optional matched mechanism pairs. Each target group needs at least two participants in each of five folds, numbered 0–4. Each evaluator must have the same complete participant set and paired replicate IDs in every condition. The optional `dataset` column separates datasets; optional `utility` must be complete and shared across evaluators. Repetitions are averaged within participant, then folds are weighted equally.

The example JSON uses schema version 2, alpha 0.05 and Holm correction. Its `seed`, `n_boot` and `n_perm` fields are inherited from a separate blocked-resampling interface and do not control this entry's approximate t inference. The shared input validator nevertheless requires matching positive `n_boot` and `n_perm`. Define conditions and comparison families before analysis.

## Report and interpretation

The reports contain condition summaries, signed group gaps, changes from baseline, mechanism and utility comparisons where specified, confidence intervals, raw and adjusted p-values, family sizes, diagnostics, a score-file hash and calibration status. The PDF also summarizes the number of passed, not-passed and withheld decisions in each family. An unestimable zero-variance test is retained in its family and its decision is withheld. The intervals are pointwise, not simultaneous intervals; a result that does not pass correction does not prove equal protection.

Inference is conditional on the supplied fitted models and galleries and assumes independent participants. The included score-level calibration summary is checked against the inference source; it does not establish independence under shared-gallery or overlapping-training dependence, nor directly establish familywise error control for every new comparison plan. Missing calibration or a changed method disables formal decisions. The audit does not verify how data were collected, split or protected, and does not establish equivalence, causal demographic effects, a privacy guarantee or the strongest possible attack. The study's noise-aware training and scoring experiments are separate from this score-table tool.

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

`src/fairness/robust_inference.py` is retained byte-for-byte from the calibrated study code. The CSV loader was extracted from the study's input adapter without its unused historical analysis functions. The executable entry and tests preserve the calibrated method and verify that Git's LF/CRLF conversion does not falsely invalidate its source identity.
