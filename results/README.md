# Results

`offline_validation.json` records the pre-call rendering and font checks. The authoritative completed model run is Kaggle task version 5, run `4630179`, on `google/gemini-3.7-flash`:

- Raw Kaggle exports: `kaggle_runs/reading-or-guessing-urdu-font-twins/5/gemini-3.7-flash/4630179/`
- Analysis-ready image predictions: `predictions_gemini_3_7_flash_v5.csv`
- Final metrics and plots: `analysis/gemini-3.7-flash-v5/`
- Machine-readable provenance: `kaggle_status.json`

The unversioned Gemini prediction file, `analysis/gemini-3.7-flash/`, and `kaggle_build_v4/` are retained for audit history but are superseded by version 5. Tesseract was unavailable locally and is reported as unavailable in `tesseract.json`; no synthetic baseline score is substituted.

The multi-model expansion is indexed by `all_models/model_run_status.csv`. Consolidated full-image predictions and plots are in `all_models/` and `analysis/all_models/`; partial runs remain in their raw Kaggle download directories and are not silently included in paired comparisons. Version 9 is the retry-ready task after the first `$10` daily quota was exhausted.
