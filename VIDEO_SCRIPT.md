# Video Script

## 1. Question

Can a vision model actually read Urdu, or is it guessing from language patterns? This benchmark changes only the font while keeping the source string exactly the same.

## 2. Paired design

Fifteen public Urdu sentences become three conditions: natural text, shuffled words, and controlled pseudo-words. Each is rendered in Nastaliq and Naskh, producing forty-five exact-text pairs and ninety images.

## 3. Rendering validation

Before any model call, HarfBuzz shapes every string right to left and FreeType renders the selected glyphs directly. Both fonts pass coverage, shaping, bounds, fallback, and pair-identity checks.

## 4. Pilot signal

For Gemini 3.7 Flash, the font gap is near zero on natural and shuffled text, then rises to eight point eight character-error points on pseudo-words. Its paired confidence interval excludes zero.

## 5. Across models

Seven models completed every image. Five show a positive pseudo-word gap with a confidence interval above zero. Two do not, which is exactly why the benchmark reports paired model-level results instead of one pooled headline.

## 6. Honest status

The available catalog contains forty-six models. Four runs are fully complete, three completed all images with partial prior controls, and other runs are pending or failed canaries. Missing scores are never invented or imputed.

## 7. Explore

The Kaggle benchmark and reproducible source are public. The next run expands the model coverage, adds lower-resolution tests, and scales the pilot from fifteen to sixty source items.

