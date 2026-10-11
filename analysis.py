"""Score predictions and analyze paired Nastaliq-minus-Naskh gaps."""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from ocr_metrics import real_word_hallucinations, score_text, urdu_words


PAIR_KEYS = ["model", "pair_id", "condition", "resolution"]


def pseudo_hallucinations(condition: str, reference: str, hypothesis: str, lexicon: set[str]) -> dict:
    if condition != "pseudo":
        return {
            "real_word_hallucination_count": 0,
            "real_word_hallucination_rate": 0.0,
            "real_word_hallucinations": [],
        }
    return real_word_hallucinations(reference, hypothesis, lexicon)


def sign_flip_test(differences: list[float], trials: int = 20000, seed: int = 20261010) -> float:
    values = [value for value in differences if not math.isnan(value)]
    if not values:
        return math.nan
    observed = abs(sum(values) / len(values))
    rng = random.Random(seed)
    exceed = 1
    for _ in range(trials):
        permuted = abs(sum(value * rng.choice((-1, 1)) for value in values) / len(values))
        exceed += permuted >= observed
    return exceed / (trials + 1)


def bootstrap_ci(differences: list[float], trials: int = 10000, seed: int = 20261010) -> tuple[float, float]:
    values = [value for value in differences if not math.isnan(value)]
    if not values:
        return math.nan, math.nan
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(trials))
    return means[round(0.025 * (trials - 1))], means[round(0.975 * (trials - 1))]


def load_and_score(manifest_path: Path, predictions_path: Path) -> pd.DataFrame:
    manifest = pd.DataFrame(json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line)
    predictions = pd.read_csv(predictions_path)
    required = {"image_id", "model", "prediction"}
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"Predictions file is missing columns: {sorted(missing)}")
    frame = manifest.merge(predictions, on="image_id", how="inner", validate="one_to_many")
    natural_lexicon = {
        word
        for text in manifest.loc[manifest["condition"] == "natural", "text"]
        for word in urdu_words(text)
    }
    metric_rows = []
    for row in frame.itertuples(index=False):
        metrics = score_text(row.text, row.prediction)
        hallucination = pseudo_hallucinations(
            row.condition, row.text, row.prediction, natural_lexicon
        )
        metric_rows.append({**metrics, **hallucination})
    return pd.concat([frame.reset_index(drop=True), pd.DataFrame(metric_rows)], axis=1)


def paired_gaps(scored: pd.DataFrame) -> pd.DataFrame:
    wide = scored.pivot_table(index=PAIR_KEYS, columns="font_key", values=["cer", "wer"], aggfunc="mean")
    wide.columns = [f"{metric}_{font}" for metric, font in wide.columns]
    wide = wide.reset_index()
    for metric in ("cer", "wer"):
        wide[f"{metric}_gap_nastaliq_minus_naskh"] = wide[f"{metric}_nastaliq"] - wide[f"{metric}_naskh"]
    return wide


def summarize_pairs(gaps: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model, condition, resolution), group in gaps.groupby(["model", "condition", "resolution"], dropna=False):
        for metric in ("cer", "wer"):
            column = f"{metric}_gap_nastaliq_minus_naskh"
            values = group[column].dropna().tolist()
            low, high = bootstrap_ci(values)
            rows.append(
                {
                    "model": model,
                    "condition": condition,
                    "resolution": resolution,
                    "metric": metric,
                    "n_pairs": len(values),
                    "mean_paired_gap": sum(values) / len(values) if values else math.nan,
                    "bootstrap_ci_low": low,
                    "bootstrap_ci_high": high,
                    "sign_flip_p_value": sign_flip_test(values),
                }
            )
    return pd.DataFrame(rows)


def aggregate_metrics(scored: pd.DataFrame) -> pd.DataFrame:
    group_keys = ["model", "condition", "font_key", "resolution"]
    return (
        scored.groupby(group_keys, dropna=False)
        .agg(
            images=("image_id", "count"),
            mean_cer=("cer", "mean"),
            mean_wer=("wer", "mean"),
            char_insertions=("char_insertions", "sum"),
            char_deletions=("char_deletions", "sum"),
            char_substitutions=("char_substitutions", "sum"),
            word_insertions=("word_insertions", "sum"),
            word_deletions=("word_deletions", "sum"),
            word_substitutions=("word_substitutions", "sum"),
            pseudo_real_word_hallucinations=("real_word_hallucination_count", "sum"),
            mean_pseudo_real_word_hallucination_rate=("real_word_hallucination_rate", "mean"),
        )
        .reset_index()
    )


def analyze_text_prior(manifest_path: Path, predictions_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest = pd.DataFrame(
        json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line
    )
    references = manifest[["pair_id", "condition", "text"]].drop_duplicates("pair_id")
    predictions = pd.read_csv(predictions_path)
    if "model" not in predictions:
        predictions["model"] = "unspecified"
    predictions = predictions[["model", "pair_id", "condition", "prediction"]]
    scored = predictions.merge(references, on=["pair_id", "condition"], validate="many_to_one")
    metrics = [score_text(row.text, row.prediction) for row in scored.itertuples(index=False)]
    scored = pd.concat([scored.reset_index(drop=True), pd.DataFrame(metrics)], axis=1)
    summary = (
        scored.groupby(["model", "condition"], dropna=False)
        .agg(
            items=("pair_id", "count"),
            mean_cer=("cer", "mean"),
            mean_wer=("wer", "mean"),
            char_insertions=("char_insertions", "sum"),
            char_deletions=("char_deletions", "sum"),
            char_substitutions=("char_substitutions", "sum"),
            word_insertions=("word_insertions", "sum"),
            word_deletions=("word_deletions", "sum"),
            word_substitutions=("word_substitutions", "sum"),
        )
        .reset_index()
    )
    return scored, summary


def make_plots(scored: pd.DataFrame, gaps: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")
    heat = scored.pivot_table(index=["model", "condition"], columns="font_key", values="cer", aggfunc="mean")
    plt.figure(figsize=(8, max(4, 0.45 * len(heat))))
    sns.heatmap(heat, annot=True, fmt=".3f", cmap="mako", vmin=0)
    plt.title("Mean character error rate")
    plt.tight_layout()
    plt.savefig(output_dir / "cer_heatmap.png", dpi=180)
    plt.close()

    plot = sns.relplot(
        data=gaps,
        x="cer_naskh",
        y="cer_nastaliq",
        hue="condition",
        col="model",
        col_wrap=min(3, gaps["model"].nunique()),
        kind="scatter",
        height=3.4,
    )
    for axis in plot.axes.flat:
        limit = max(axis.get_xlim()[1], axis.get_ylim()[1])
        axis.plot([0, limit], [0, limit], linestyle="--", color="black", linewidth=0.8)
        axis.set_xlim(0, limit)
        axis.set_ylim(0, limit)
    plot.set_axis_labels("Naskh CER", "Nastaliq CER")
    plot.figure.savefig(output_dir / "paired_font_comparison.png", dpi=180, bbox_inches="tight")
    plt.close(plot.figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("assets/manifest.jsonl"))
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--text-prior", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("results/analysis"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scored = load_and_score(args.manifest, args.predictions)
    gaps = paired_gaps(scored)
    summary = summarize_pairs(gaps)
    aggregates = aggregate_metrics(scored)
    scored.to_csv(args.output_dir / "scored_predictions.csv", index=False, encoding="utf-8-sig")
    aggregates.to_csv(args.output_dir / "aggregate_metrics.csv", index=False, encoding="utf-8-sig")
    gaps.to_csv(args.output_dir / "paired_gaps.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(args.output_dir / "paired_tests.csv", index=False, encoding="utf-8-sig")
    if args.text_prior:
        prior_scored, prior_summary = analyze_text_prior(args.manifest, args.text_prior)
        prior_scored.to_csv(args.output_dir / "text_prior_scored.csv", index=False, encoding="utf-8-sig")
        prior_summary.to_csv(args.output_dir / "text_prior_summary.csv", index=False, encoding="utf-8-sig")
    make_plots(scored, gaps, args.output_dir)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
