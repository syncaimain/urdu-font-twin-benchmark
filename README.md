# Reading or Guessing? Urdu Font-Twin Benchmark

This benchmark tests whether the **same Unicode Urdu text** is transcribed differently when rendered in Nastaliq versus Naskh, and whether the paired gap grows as language predictability is removed.

The checked-in pilot uses 15 revision-pinned source sentences, three conditions, and two fonts: 45 exact-text font pairs / 90 canonical images. The full design scales to 60 source items (360 canonical images). Optional downsampled variants support resolution analysis without changing the canonical set.

## Experimental design

- `natural`: a public Urdu Wikipedia sentence.
- `shuffled`: the same whitespace-delimited words in a deterministic shuffled order.
- `pseudo`: deterministic replacements using only Urdu letters while preserving spaces, punctuation, and per-token letter counts.
- Fonts: Noto Nastaliq Urdu and Noto Naskh Arabic, both under the SIL Open Font License 1.1.
- Pairing unit: source item × condition × resolution. Both font members contain the exact same normalized string and SHA-256.
- Prompt: identical across fonts and does not contain the source text.
- Primary outcome: paired Nastaliq-minus-Naskh CER. WER and edit types are secondary outcomes.

## Sources and permissions

Pilot sentences come from Urdu Wikipedia through the MediaWiki API. Every source row records a page URL, revision ID, revision URL, timestamp, and CC BY-SA 4.0 attribution metadata in `assets/source/urdu_wikipedia.json`.

The [Urdu Newspaper Benchmark paper](https://aclanthology.org/2026.lrec-1.235/) reports 829 paragraph images and 9,982 sentences. Its [public repository](https://github.com/paper-seven/UrduOCR) links a Google Drive dataset, but the repository currently exposes no dataset license. Consequently, this pilot does **not** redistribute or derive text from UNB. Add UNB examples only after the rights holder publishes or confirms reuse terms.

## Reproduce the offline pilot

Use Python 3.11–3.13. The project-local `.render-deps` and `.deps` directories are only workspace conveniences for rendering and the Kaggle CLI, respectively.

```powershell
python -m pip install -r requirements.txt
python source_data.py
python build_dataset.py
python validate_fonts.py
python -m pytest -q
```

Generate additional deterministic resolution variants when needed:

```powershell
python build_dataset.py --resolution-scales 1.0 0.5 0.25
```

The renderer uses HarfBuzz with explicit `rtl`, `Arab`, and `ur` properties, then rasterizes those glyph IDs directly with FreeType. It never asks the operating system to select a font, so font fallback is structurally impossible. `assets/font_calibration.json` records per-font pixel sizes chosen against a shared calibration string to equalize visible line height instead of point size.

Review `assets/contact_sheets/pilot_contact_sheet.png` before any endpoint run. `validate_fonts.py` fails on missing cmap coverage, absent GSUB/GPOS, failed RTL shaping, blank/out-of-bounds renders, incomplete pairs, or Unicode mismatches.

## Kaggle Benchmarks

`benchmark.py` uses the current multimodal API:

```python
image = images.from_path(image_path)
response = llm.prompt(TRANSCRIPTION_PROMPT, image=image, seed=0, temperature=0)
```

The local decorated tasks are:

- `urdu_font_twin_vision_canary`: must pass both a large number and short Urdu word image before evaluation.
- `urdu_font_twin_transcription`: the actual hidden-reference image transcription task.
- `urdu_font_twin_text_prior_control`: reconstructs a separately labeled 50%-masked text input without an image.

`package_kaggle.py` builds a flat upload directory and `kaggle_task.py` is the server task. The pilot dataset is uploaded privately at `huzaifa12344/urdu-font-twin-pilot`, including the notebook-ready task script. In the Kaggle Benchmark editor, attach that dataset and run:

```python
%run /kaggle/input/urdu-font-twin-pilot/kaggle_task.py
```

Kaggle CLI OAuth and the Benchmarks model proxy are authenticated for `huzaifa12344`. Private task version 5 completed on `google/gemini-3.7-flash`: both corrected vision canaries passed, all 90 image prompts completed, and all 45 text-prior controls completed. Raw downloaded outputs are under `results/kaggle_runs/reading-or-guessing-urdu-font-twins/5/gemini-3.7-flash/4630179`; its analysis is under `results/analysis/gemini-3.7-flash-v5`.

The all-model expansion queried Kaggle's current 46-model catalog. Cross-version results are consolidated by `collect_kaggle_results.py` into `results/all_models`, and image-complete models are analyzed in `results/analysis/all_models`. Task version 9 raises the canary token allowance for reasoning models and reports prior-control failures explicitly. The first expansion day exhausted the `$10` daily AI quota: 4 models are fully complete, 3 have all 90 images with partial prior controls, 3 have partial image runs, 28 were stopped by vision canaries, and 8 were not scheduled before the concurrency cap. A one-time local task, `UrduFontTwinQuotaResume`, is registered for the next quota refill to retry only unresolved or configuration-affected models. See `results/kaggle_status.json` and `results/all_models/model_run_status.csv` for exact provenance; no missing score is imputed.

Run canaries per endpoint and mark failures separately; do not fold them into OCR scores. The Kaggle library is expected to be preinstalled in a benchmark-connected notebook. Never commit or paste Kaggle tokens; use `kaggle auth login` for the browser-based OAuth flow.

## Baselines

`python benchmark.py --tesseract` runs Tesseract only when both the executable and the `urd` language pack are installed; otherwise it writes an explicit unavailable status. The UrduOCR public model is not run because its linked artifact has no verified license in the public repository. No placeholder score is emitted.

## Predictions and analysis

Export real model outputs as a UTF-8 CSV with columns `image_id,model,prediction`. Then run:

```powershell
python analysis.py `
  --predictions results/predictions.csv `
  --text-prior results/text_prior_predictions.csv
```

Outputs include item-level CER/WER and insertions/deletions/substitutions, pseudo-word-to-real-word hallucination rates, `paired_gaps.csv`, paired bootstrap confidence intervals, deterministic paired sign-flip tests, `cer_heatmap.png`, and `paired_font_comparison.png`. If multiple resolution variants are present, tests are stratified by resolution.

### Completed pilot result

For Gemini 3.7 Flash, the paired Nastaliq-minus-Naskh CER gap was `0.00175` for natural text, `0.00252` for shuffled text, and `0.08751` for pseudo-words. The pseudo-word CER gap had a paired bootstrap 95% interval of `[0.04052, 0.12821]` and a deterministic sign-flip p-value of `0.00290`; its paired WER gap was `0.40891`. The corresponding natural and shuffled CER intervals included zero. Nastaliq pseudo-word predictions introduced 9 natural-lexicon words absent from their references, versus 0 for Naskh. These are pilot results from 15 source items and one model, so they support expanding the experiment but do not establish a general model-independent effect.

Multi-model results remain provisional until the quota-resume run completes. The current combined analysis contains seven models with all 90 image predictions and deliberately excludes partial image runs from paired plots.

## Unicode policy

Scoring applies Unicode NFC, trims boundaries, and collapses whitespace. It does **not** fold Urdu and Arabic code points that can be genuinely distinct, including `ی/ي`, `ک/ك`, or `ہ/ھ`. Punctuation and spaces remain part of CER. This strict policy should be reported with every result table.

## Interpretation safeguards

- Treat the font effect as paired; aggregate CER alone cannot test the hypothesis.
- Keep natural, shuffled, and pseudo conditions separate in every table.
- Report endpoint canary failures and missing predictions rather than imputing them.
- A larger pseudo-word gap is consistent with reliance on language priors, but is not by itself a causal proof.
- Inspect the contact sheet and font-validation report before spending model quota.
