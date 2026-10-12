# %%
"""Kaggle Benchmarks task for the Urdu font-twin benchmark."""

import os
import re
import unicodedata
from pathlib import Path

os.environ.setdefault("RENDER_SUBRUNS", "False")

import kaggle_benchmarks as kbench
import pandas as pd
from kaggle_benchmarks.content_types import images


DATASET_CANDIDATES = [
    Path("/kaggle/input/urdu-font-twin-60"),
    Path("/kaggle/input/datasets/huzaifa12344/urdu-font-twin-60"),
    Path("/kaggle/input/huzaifa12344/urdu-font-twin-60"),
    Path("/kaggle/input/urdu-font-twin-pilot"),
    Path("/kaggle/input/datasets/huzaifa12344/urdu-font-twin-pilot"),
    Path("/kaggle/input/huzaifa12344/urdu-font-twin-pilot"),
]
dataset_roots = [
    path
    for path in DATASET_CANDIDATES
    if (path / "manifest.csv").is_file() and (path / "canaries.csv").is_file()
]
if not dataset_roots:
    dataset_roots = [
        manifest.parent
        for manifest in Path("/kaggle/input").rglob("manifest.csv")
        if (manifest.parent / "canaries.csv").is_file()
    ]
if len(dataset_roots) != 1:
    raise FileNotFoundError(
        "Expected exactly one attached Urdu font-twin dataset containing "
        f"manifest.csv and canaries.csv; found {len(dataset_roots)}."
    )
DATASET_ROOT = dataset_roots[0]

MASK_CHAR = "\u25a1"
TRANSCRIPTION_PROMPT = (
    "Transcribe the Urdu text in this image exactly as it appears. "
    "Return only the transcription, with no explanation, quotation marks, or translation."
)
CANARY_PROMPT = "Read the content of this image exactly. Return only what is shown."
CANARY_MAX_OUTPUT_TOKENS = 256
TRANSCRIPTION_MAX_OUTPUT_TOKENS = 384
PRIOR_MAX_OUTPUT_TOKENS = 384


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", str(text)).strip().split())


def edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, ref_item in enumerate(reference, start=1):
        current = [row]
        for column, hyp_item in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (ref_item != hyp_item),
                )
            )
        previous = current
    return previous[-1]


def score(reference: str, hypothesis: str) -> tuple[float, float]:
    reference = normalize(reference)
    hypothesis = normalize(hypothesis)
    cer = edit_distance(list(reference), list(hypothesis)) / max(1, len(reference))
    wer = edit_distance(reference.split(), hypothesis.split()) / max(1, len(reference.split()))
    return cer, wer


def masked_prior_text(text: str) -> str:
    output = []
    index = 0
    for char in normalize(text):
        if "\u0600" <= char <= "\u08ff":
            output.append(char if index % 2 == 0 else MASK_CHAR)
            index += 1
        else:
            output.append(char)
    return "".join(output)


# %%
@kbench.task(name="urdu-font-twin-canary", store_task=False)
def vision_canary(llm, image_file: str, expected: str, canary_id: str) -> dict:
    image = images.from_path(str(DATASET_ROOT / image_file))
    response = llm.prompt(
        CANARY_PROMPT,
        image=image,
        seed=0,
        temperature=0,
        extra_api_params={"max_tokens": CANARY_MAX_OUTPUT_TOKENS},
    )
    passed = normalize(response) == normalize(expected)
    kbench.assertions.assert_contains_regex(
        f"^{re.escape(normalize(expected))}$",
        normalize(response),
        expectation=f"Endpoint must pass {canary_id} before OCR evaluation.",
    )
    return {"canary_id": canary_id, "response": response, "passed": passed}


@kbench.task(name="urdu-font-twin-item", store_task=False)
def transcribe_item(
    llm,
    image_id: str,
    image_file: str,
    pair_id: str,
    source_id: str,
    condition: str,
    font_key: str,
    resolution: str,
    expected_text: str,
    text_sha256: str,
) -> dict:
    image = images.from_path(str(DATASET_ROOT / image_file))
    response = llm.prompt(
        TRANSCRIPTION_PROMPT,
        image=image,
        seed=0,
        temperature=0,
        extra_api_params={"max_tokens": TRANSCRIPTION_MAX_OUTPUT_TOKENS},
    )
    kbench.assertions.assert_contains_regex(r"\S", response, expectation="Transcription must not be empty.")
    cer, wer = score(expected_text, response)
    return {
        "image_id": image_id,
        "pair_id": pair_id,
        "source_id": source_id,
        "condition": condition,
        "font_key": font_key,
        "resolution": resolution,
        "text_sha256": text_sha256,
        "prediction": response,
        "cer": cer,
        "wer": wer,
    }


@kbench.task(name="urdu-font-twin-text-prior", store_task=False)
def text_prior_item(llm, pair_id: str, condition: str, expected_text: str) -> dict:
    masked = masked_prior_text(expected_text)
    prompt = (
        f"Fill each {MASK_CHAR} in this partially masked Urdu text. "
        "Return only the reconstructed text.\n\n" + masked
    )
    response = llm.prompt(
        prompt,
        seed=0,
        temperature=0,
        extra_api_params={"max_tokens": PRIOR_MAX_OUTPUT_TOKENS},
    )
    cer, wer = score(expected_text, response)
    return {"pair_id": pair_id, "condition": condition, "prediction": response, "cer": cer, "wer": wer}


def paired_gaps(items: pd.DataFrame) -> dict:
    if items.empty:
        return {}
    wide = items.pivot_table(
        index=["pair_id", "condition", "resolution"], columns="font_key", values="cer", aggfunc="mean"
    ).dropna(subset=["nastaliq", "naskh"])
    wide["gap"] = wide["nastaliq"] - wide["naskh"]
    return {condition: float(group["gap"].mean()) for condition, group in wide.groupby("condition")}


# %%
@kbench.task(
    name="Reading or Guessing Urdu Font Twins",
    description="Paired Urdu OCR across Nastaliq/Naskh font twins and language conditions.",
)
def urdu_font_twin_benchmark(llm) -> dict:
    canaries = pd.read_csv(DATASET_ROOT / "canaries.csv", dtype=str).fillna("")
    canary_runs = vision_canary.evaluate(llm=[llm], evaluation_data=canaries, n_jobs=1, on_failure="continue")
    canary_frame = canary_runs.as_dataframe()
    canary_results = [value for value in canary_frame.result.tolist() if isinstance(value, dict)]
    canary_passed = (
        len(canary_runs.errored_runs) == 0
        and len(canary_results) == len(canaries)
        and all(value.get("passed", False) for value in canary_results)
    )
    kbench.assertions.assert_true(canary_passed, expectation="Both vision canaries must pass.")
    if not canary_passed:
        return {
            "status": "vision_canary_failed",
            "canaries_completed": len(canary_results),
            "canary_errors": len(canary_runs.errored_runs),
        }

    manifest = pd.read_csv(DATASET_ROOT / "manifest.csv", dtype=str).fillna("")
    with kbench.client.enable_cache():
        runs = transcribe_item.evaluate(
            llm=[llm],
            evaluation_data=manifest,
            n_jobs=3,
            timeout=600,
            on_failure="continue",
            max_attempts=2,
            retry_delay=15,
        )
    completed = runs.completed_runs.as_dataframe()
    item_results = pd.DataFrame(completed.result.tolist()) if not completed.empty else pd.DataFrame()
    item_results.to_csv("urdu_font_twin_predictions.csv", index=False, encoding="utf-8-sig")

    prior_data = manifest[["pair_id", "condition", "expected_text"]].drop_duplicates("pair_id")
    with kbench.client.enable_cache():
        prior_runs = text_prior_item.evaluate(
            llm=[llm],
            evaluation_data=prior_data,
            n_jobs=3,
            timeout=600,
            on_failure="continue",
            max_attempts=2,
            retry_delay=15,
        )
    prior_completed = prior_runs.completed_runs.as_dataframe()
    prior_results = pd.DataFrame(prior_completed.result.tolist()) if not prior_completed.empty else pd.DataFrame()
    prior_results.to_csv("urdu_text_prior_predictions.csv", index=False, encoding="utf-8-sig")

    image_failures = len(runs.errored_runs)
    prior_failures = len(prior_runs.errored_runs)
    return {
        "status": "complete" if image_failures == 0 and prior_failures == 0 else "partial",
        "vision_canary_passed": True,
        "completed_images": len(item_results),
        "failed_images": image_failures,
        "mean_cer": float(item_results.cer.mean()) if not item_results.empty else None,
        "mean_wer": float(item_results.wer.mean()) if not item_results.empty else None,
        "paired_cer_gap_nastaliq_minus_naskh": paired_gaps(item_results),
        "text_prior_completed": len(prior_results),
        "text_prior_failed": prior_failures,
        "text_prior_mean_cer": float(prior_results.cer.mean()) if not prior_results.empty else None,
    }


urdu_font_twin_benchmark.run(kbench.llm)
