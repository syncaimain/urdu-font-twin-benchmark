"""Consolidate Kaggle Benchmark run downloads without hiding partial runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def result_dict(run_file: Path) -> dict:
    payload = json.loads(run_file.read_text(encoding="utf-8"))
    for result in payload.get("results", []):
        if "dictResult" in result:
            return result["dictResult"]
    return {}


def classify(result: dict) -> str:
    if result.get("status") == "vision_canary_failed":
        return "vision_canary_failed"
    images = int(result.get("completed_images") or 0)
    priors = int(result.get("text_prior_completed") or 0)
    image_failures = int(result.get("failed_images") or 0)
    if images == 90 and image_failures == 0 and priors == 45:
        return "complete"
    if images == 90 and image_failures == 0:
        return "image_complete_prior_partial"
    if images:
        return "image_partial"
    return "run_error"


def canary_failure_reason(run_dir: Path, result: dict) -> str:
    if result.get("status") != "vision_canary_failed":
        return ""
    errors = []
    responses = []
    for path in run_dir.glob("urdu-font-twin-canary*.run.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        errors.append(payload.get("errorMessage", ""))
        child = result_dict(path)
        if "response" in child:
            responses.append(str(child["response"]))
    error_text = " ".join(errors).lower()
    if "quota" in error_text:
        return "quota_error"
    if "unexpected keyword argument" in error_text:
        return "task_configuration_error"
    if "image" in error_text and ("not support" in error_text or "unsupported" in error_text):
        return "vision_unsupported"
    if any(errors):
        return "canary_api_error"
    if responses and all(not response.strip() for response in responses):
        return "empty_response_under_token_cap"
    return "canary_transcription_mismatch"


def rank(row: dict) -> tuple[int, int, int, int]:
    order = {
        "complete": 4,
        "image_complete_prior_partial": 3,
        "image_partial": 2,
        "vision_canary_failed": 1,
        "run_error": 0,
    }
    return order[row["classification"]], row["completed_images"], row["text_prior_completed"], row["version"]


def discover(roots: list[Path]) -> list[dict]:
    rows = []
    for root in roots:
        version = int(root.name)
        for model_dir in root.iterdir():
            if not model_dir.is_dir():
                continue
            for run_dir in model_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                main_files = list(run_dir.glob("Reading_or_Guessing*.run.json"))
                if not main_files:
                    continue
                result = result_dict(main_files[0])
                row = {
                    "model": model_dir.name,
                    "version": version,
                    "run_id": int(run_dir.name),
                    "classification": classify(result),
                    "canary_failure_reason": canary_failure_reason(run_dir, result),
                    "vision_canary_passed": bool(result.get("vision_canary_passed", False)),
                    "completed_images": int(result.get("completed_images") or 0),
                    "failed_images": int(result.get("failed_images") or 0),
                    "text_prior_completed": int(result.get("text_prior_completed") or 0),
                    "text_prior_failed": int(result.get("text_prior_failed") or 0),
                    "run_directory": str(run_dir),
                }
                rows.append(row)
    return rows


def consolidate(roots: list[Path], expected_models: Path, output_dir: Path) -> None:
    discovered = discover(roots)
    best = {}
    for row in discovered:
        if row["model"] not in best or rank(row) > rank(best[row["model"]]):
            best[row["model"]] = row
    expected = [line.strip() for line in expected_models.read_text(encoding="utf-8").splitlines() if line.strip()]
    status_rows = []
    for model in expected:
        status_rows.append(best.get(model, {"model": model, "classification": "unscheduled"}))
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(status_rows).to_csv(output_dir / "model_run_status.csv", index=False, encoding="utf-8-sig")

    image_frames = []
    prior_frames = []
    for row in best.values():
        run_dir = Path(row["run_directory"])
        if row["completed_images"] == 90 and row["failed_images"] == 0:
            path = run_dir / "urdu_font_twin_predictions.csv"
            if path.is_file():
                frame = pd.read_csv(path)
                frame["model"] = row["model"]
                image_frames.append(frame[["image_id", "model", "prediction"]])
        if row["text_prior_completed"] == 45:
            path = run_dir / "urdu_text_prior_predictions.csv"
            if path.is_file():
                frame = pd.read_csv(path)
                frame["model"] = row["model"]
                prior_frames.append(frame[["model", "pair_id", "condition", "prediction"]])
    if image_frames:
        pd.concat(image_frames, ignore_index=True).to_csv(
            output_dir / "all_model_predictions.csv", index=False, encoding="utf-8-sig"
        )
    if prior_frames:
        pd.concat(prior_frames, ignore_index=True).to_csv(
            output_dir / "all_model_text_prior_predictions.csv", index=False, encoding="utf-8-sig"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, action="append", required=True)
    parser.add_argument("--expected-models", type=Path, default=Path("assets/kaggle_models.txt"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/all_models"))
    args = parser.parse_args()
    consolidate(args.run_root, args.expected_models, args.output_dir)


if __name__ == "__main__":
    main()
