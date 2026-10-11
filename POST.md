---
title: "Reading or Guessing? An Urdu Font-Twin Benchmark"
published: false
description: "The same Urdu Unicode string, two writing styles, and one paired test of whether multimodal models read glyphs or lean on language priors."
tags: kagglechallenge, machinelearning, computervision, ocr
cover_image: https://raw.githubusercontent.com/hassan-2050/urdu-font-twin-benchmark/main/media/cover.png
---

*This is a submission for the [Kaggle Benchmarking Challenge](https://dev.to/challenges/kaggle-2026-09-23).*

Urdu OCR has an unusually revealing stress test built into its typography. Nastaliq is diagonal, context-heavy, and visually dense; Naskh is more linear. If a multimodal model is truly reading the glyphs, changing only the font should not change its transcription very much. If it is filling gaps with language priors, the difference may grow when the text stops being predictable.

That led to one deliberately narrow question:

> Will a model transcribe the exact same Urdu Unicode string differently when it is rendered in Nastaliq instead of Naskh?

![The same pseudo-Urdu source rendered in Nastaliq and Naskh](https://raw.githubusercontent.com/hassan-2050/urdu-font-twin-benchmark/main/media/screenshots/01-font-twins.png)

## What I Benchmarked

I built a paired multimodal OCR benchmark with three language conditions:

1. **Natural:** revision-pinned Urdu Wikipedia sentences.
2. **Shuffled:** the same words in a deterministic shuffled order.
3. **Pseudo:** deterministic Urdu-like character sequences that preserve spaces, punctuation, and token lengths while removing ordinary word predictability.

Every item is rendered twice: once in **Noto Nastaliq Urdu** and once in **Noto Naskh Arabic**. The two images in a pair contain the exact same NFC-normalized Unicode string and share a source-text SHA-256. The prompt is also identical: transcribe only what is visible, with no source text or font hint supplied to the model.

The pilot has **15 source items x 3 conditions x 2 fonts = 90 images**, organized as 45 exact-text font pairs.

![Pilot design](https://raw.githubusercontent.com/hassan-2050/urdu-font-twin-benchmark/main/media/screenshots/02-experimental-design.png)

### Rendering was part of the experiment

This benchmark would be meaningless if one font silently fell back, clipped glyphs, or simply rendered smaller. Before making model calls, I therefore:

- shaped every string with HarfBuzz using explicit `rtl`, `Arab`, and `ur` properties;
- rasterized those glyph IDs directly with FreeType, preventing operating-system font fallback;
- verified character coverage, GSUB/GPOS tables, ligatures, RTL cluster order, image bounds, and nonblank output;
- calibrated each font against visible text height instead of assigning the same nominal point size; and
- generated a contact sheet for human inspection.

Offline validation passed all **90 images and 45 pairs**, with no missing codepoints, fallback, Unicode mismatch, clipping, or blank render.

The text is public and traceable. Each natural sentence records its Urdu Wikipedia page URL and revision ID under CC BY-SA 4.0. I did **not** add examples from the Urdu Newspaper Benchmark because its linked public data did not expose a dataset license that I could verify.

### Scoring policy

The primary metric is paired **Nastaliq CER minus Naskh CER**. A positive gap means the model made more character errors on Nastaliq for the same source string. I also compute WER, insertions, deletions, substitutions, pseudo-word hallucinations into real words, paired bootstrap confidence intervals, and paired sign-flip tests.

Scoring uses Unicode NFC and whitespace normalization. It does not merge distinct Urdu and Arabic letters such as U+06CC/U+064A, U+06A9/U+0643, or U+06C1/U+06BE.

Two simple vision canaries, a large number and a short Urdu word, run before the benchmark. Endpoints that fail them are reported separately instead of being assigned an OCR score.

## Models Tested

I queried Kaggle's available 46-model catalog. The first expansion pass reached Kaggle's daily AI quota, so the current paired analysis includes the seven endpoints that completed all 90 image prompts:

- Anthropic Claude Haiku 4.5
- Anthropic Claude Haiku 5.5
- Anthropic Claude Sonnet 5
- Anthropic Claude Sonnet 5.5
- Google Gemini 3.5 Flash-Lite
- Google Gemini 3.7 Flash
- OpenAI GPT-5.4 Mini

Four of these also completed all 45 masked text-only prior controls. Partial image runs are retained for audit but excluded from the paired plots. Missing results are never imputed. The retry task uses a larger canary token allowance for reasoning models and will continue after quota refresh.

That incompleteness is worth stating plainly: this is a **validated pilot and an in-progress 46-model evaluation**, not a finished universal ranking.

## Findings

The clearest completed run was Gemini 3.7 Flash. Its mean Nastaliq-minus-Naskh CER gap was:

| Condition | Paired CER gap | 95% bootstrap interval |
|---|---:|---:|
| Natural | +0.18 points | [0.00, 0.47] points |
| Shuffled | +0.25 points | [0.00, 0.54] points |
| Pseudo | **+8.75 points** | **[4.05, 12.82] points** |

Its pseudo-word WER gap was **+40.89 points**. Nastaliq pseudo-word outputs introduced nine natural-lexicon words absent from the references; Naskh introduced none. For this model, removing linguistic predictability exposed a much larger font gap than the natural and shuffled conditions.

![Character error rate heatmap](https://raw.githubusercontent.com/hassan-2050/urdu-font-twin-benchmark/main/media/screenshots/03-cer-heatmap.png)

The multi-model picture is more interesting than a single clean headline:

| Image-complete model | Pseudo CER gap | 95% bootstrap interval |
|---|---:|---:|
| Claude Haiku 4.5 | +21.8 points | [17.0, 26.6] |
| Claude Haiku 5.5 | +4.9 points | [-6.5, 15.6] |
| Claude Sonnet 5.5 | +35.9 points | [16.4, 57.0] |
| Claude Sonnet 5 | -12.5 points | [-33.5, 10.2] |
| Gemini 3.5 Flash-Lite | +12.9 points | [9.8, 16.3] |
| Gemini 3.7 Flash | +8.8 points | [4.1, 12.8] |
| GPT-5.4 Mini | +12.0 points | [8.6, 14.9] |

Five of seven image-complete models had a positive pseudo-word interval excluding zero. Two did not support that direction, including one negative point estimate with a wide interval. Several Claude runs also showed substantial gaps on natural or shuffled text, which warns against reducing every font effect to language-prior reliance.

![Paired font comparison](https://raw.githubusercontent.com/hassan-2050/urdu-font-twin-benchmark/main/media/screenshots/04-paired-font-comparison.png)

### What surprised me

I expected pseudo-words to be harder. I did not expect the **difference between fonts** to expand so sharply for several models while remaining small or unstable for others. The font is not just cosmetic input formatting; for some multimodal systems it changes the effective task.

The canaries were also informative. A model name appearing in a multimodal catalog does not guarantee that an endpoint will accept images, allocate enough visible output tokens, or follow an exact-transcription instruction. Separating endpoint failures from OCR errors prevented infrastructure behavior from becoming a fake accuracy score.

### What I would measure next

The next run will complete the retry-eligible endpoints, add 0.5x and 0.25x resolution strata, and increase the source set from 15 to 60 items. I also want to add Tesseract Urdu and a public UrduOCR checkpoint, but only when the executable/model artifact and its reuse license are verifiably available. The core analysis will remain paired: the question is not merely which model has lower CER, but whether the *same model reading the same string* changes when only its Urdu font changes.

## Video Walkthrough

{% youtube wQcnfXLtA-E %}

[Watch the walkthrough on YouTube](https://youtu.be/wQcnfXLtA-E), or [download the two-minute MP4 from GitHub](https://github.com/hassan-2050/urdu-font-twin-benchmark/raw/main/media/urdu-font-twin-walkthrough.mp4).

## My Benchmark

The Kaggle task, code, reproducible assets, font-validation report, and current run history are here:

- **Kaggle Benchmark:** [Reading or Guessing? Urdu Font Twins, version 9](https://www.kaggle.com/benchmarks/tasks/huzaifa12344/reading-or-guessing-urdu-font-twins/9)
- **Source and reproducibility bundle:** [hassan-2050/urdu-font-twin-benchmark](https://github.com/hassan-2050/urdu-font-twin-benchmark)

The repository includes the deterministic renderer, source manifest, font licenses, canaries, metric implementation, analysis scripts, tests, contact sheet, and machine-readable status ledger. No benchmark score in this post is estimated or filled in from missing data.

The experiment started with a typography question, but it ended up probing something broader: when a vision-language model produces the right word, how much of that answer came from seeing the letters, and how much came from knowing what word ought to be there?
