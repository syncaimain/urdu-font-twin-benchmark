"""Kaggle Benchmarks multimodal tasks and local baseline helpers."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from ocr_metrics import normalize_urdu, score_text


TRANSCRIPTION_PROMPT = (
    "Transcribe the Urdu text in this image exactly as it appears. "
    "Return only the transcription, with no explanation, quotation marks, or translation."
)
CANARY_PROMPT = "Read the content of this image exactly. Return only what is shown."
CANARY_MAX_OUTPUT_TOKENS = 256
TRANSCRIPTION_MAX_OUTPUT_TOKENS = 384
PRIOR_MAX_OUTPUT_TOKENS = 384

try:
    import kaggle_benchmarks as kbench
    from kaggle_benchmarks.content_types import images

    KAGGLE_BENCHMARKS_AVAILABLE = True
except ImportError:
    kbench = None
    images = None
    KAGGLE_BENCHMARKS_AVAILABLE = False


def _task(name: str):
    if KAGGLE_BENCHMARKS_AVAILABLE:
        return kbench.task(name=name)
    return lambda function: function


@_task(name="urdu_font_twin_transcription")
def transcribe_urdu(llm, image_path: str):
    """Transcribe one hidden-reference Urdu image using the official image API."""
    image = images.from_path(image_path)
    return llm.prompt(
        TRANSCRIPTION_PROMPT,
        image=image,
        seed=0,
        temperature=0,
        extra_api_params={"max_tokens": TRANSCRIPTION_MAX_OUTPUT_TOKENS},
    )


@_task(name="urdu_font_twin_vision_canary")
def vision_canary(llm, image_path: str, expected: str):
    """Gate an endpoint on simple visual reading before benchmark evaluation."""
    image = images.from_path(image_path)
    response = llm.prompt(
        CANARY_PROMPT,
        image=image,
        seed=0,
        temperature=0,
        extra_api_params={"max_tokens": CANARY_MAX_OUTPUT_TOKENS},
    )
    passed = normalize_urdu(response) == normalize_urdu(expected)
    if KAGGLE_BENCHMARKS_AVAILABLE:
        kbench.assertions.assert_contains_regex(
            f"^{re.escape(normalize_urdu(expected))}$",
            normalize_urdu(response),
            expectation="The endpoint must pass the vision canary exactly.",
        )
    return response


def mask_for_text_prior(text: str) -> str:
    output = []
    visible_index = 0
    for char in text:
        if "\u0600" <= char <= "\u08ff":
            output.append(char if visible_index % 2 == 0 else "□")
            visible_index += 1
        else:
            output.append(char)
    return "".join(output)


@_task(name="urdu_font_twin_text_prior_control")
def text_only_prior(llm, masked_text: str):
    prompt = (
        "Fill each □ in this partially masked Urdu text. Return only the reconstructed text.\n\n"
        + masked_text
    )
    return llm.prompt(
        prompt,
        seed=0,
        temperature=0,
        extra_api_params={"max_tokens": PRIOR_MAX_OUTPUT_TOKENS},
    )


def tesseract_status() -> dict:
    executable = shutil.which("tesseract")
    if not executable:
        return {"available": False, "reason": "tesseract executable not found"}
    result = subprocess.run([executable, "--list-langs"], capture_output=True, text=True, check=False)
    languages = set(result.stdout.splitlines()[1:])
    return {
        "available": "urd" in languages,
        "executable": executable,
        "languages": sorted(languages),
        "reason": None if "urd" in languages else "Urdu language pack 'urd' not installed",
    }


def run_tesseract(manifest_path: Path, output_path: Path) -> None:
    status = tesseract_status()
    if not status["available"]:
        output_path.write_text(json.dumps({"status": status}, indent=2) + "\n", encoding="utf-8")
        return
    rows = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        result = subprocess.run(
            [status["executable"], item["image_path"], "stdout", "-l", "urd", "--psm", "6"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        rows.append({"image_id": item["image_id"], "prediction": result.stdout.strip(), **score_text(item["text"], result.stdout)})
    output_path.write_text(json.dumps({"status": status, "rows": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tesseract", action="store_true")
    parser.add_argument("--manifest", type=Path, default=Path("assets/manifest.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("results/tesseract.json"))
    args = parser.parse_args()
    if args.tesseract:
        run_tesseract(args.manifest, args.output)
    else:
        print(json.dumps({"kaggle_benchmarks_available": KAGGLE_BENCHMARKS_AVAILABLE, "tesseract": tesseract_status()}, indent=2))


if __name__ == "__main__":
    main()
