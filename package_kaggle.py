"""Build a flat Kaggle dataset directory from a versioned font-twin manifest."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def build_package(
    manifest_path: Path,
    staging: Path,
    sources_path: Path,
    summary_path: Path,
    validation_path: Path,
    contact_sheet_path: Path,
    dataset_ref: str,
) -> None:
    staging.mkdir(parents=True, exist_ok=True)
    rows = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if not rows:
        raise ValueError(f"Manifest is empty: {manifest_path}")

    output_rows = []
    for row in rows:
        source = ROOT / row["image_path"]
        image_file = source.name
        shutil.copy2(source, staging / image_file)
        output_rows.append(
            {
                "image_id": row["image_id"],
                "image_file": image_file,
                "pair_id": row["pair_id"],
                "source_id": row["source_id"],
                "condition": row["condition"],
                "font_key": row["font_key"],
                "resolution": row["resolution"],
                "expected_text": row["text"],
                "text_sha256": row["text_sha256"],
            }
        )
    with (staging / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    canaries = json.loads((ROOT / "assets/canaries/manifest.json").read_text(encoding="utf-8"))
    canary_rows = []
    for row in canaries:
        source = ROOT / row["image_path"]
        image_file = f"canary_{source.name}"
        shutil.copy2(source, staging / image_file)
        canary_rows.append(
            {"canary_id": row["canary_id"], "expected": row["expected"], "image_file": image_file}
        )
    with (staging / "canaries.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["canary_id", "expected", "image_file"])
        writer.writeheader()
        writer.writerows(canary_rows)

    copies = {
        ROOT / "kaggle_task.py": "kaggle_task.py",
        summary_path: "dataset_summary.json",
        ROOT / "assets/font_calibration.json": "font_calibration.json",
        validation_path: "offline_validation.json",
        sources_path: "urdu_wikipedia_sources.json",
        manifest_path: "manifest.jsonl",
    }
    for source, target in copies.items():
        shutil.copy2(source, staging / target)

    contact_pattern = f"{contact_sheet_path.stem}*{contact_sheet_path.suffix}"
    contact_sheets = sorted(contact_sheet_path.parent.glob(contact_pattern))
    if not contact_sheets:
        raise FileNotFoundError(f"No contact sheets matched {contact_sheet_path}")
    for source in contact_sheets:
        shutil.copy2(source, staging / source.name)

    metadata = {
        "title": "Urdu Font-Twin Benchmark - 60 Sources",
        "id": dataset_ref,
        "licenses": [{"name": "CC-BY-SA-4.0"}],
    }
    (staging / "dataset-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    readme = (
        "# Urdu Font-Twin Benchmark\n\n"
        f"- Sources: {summary['source_items']}\n"
        f"- Exact-text font pairs: {summary['font_pairs']}\n"
        f"- Canonical images: {summary['images']}\n"
        "- Text source: revision-pinned Urdu Wikipedia excerpts under CC BY-SA 4.0\n"
        "- Fonts: Noto Nastaliq Urdu and Noto Naskh Arabic under OFL 1.1\n"
    )
    (staging / "README.md").write_text(readme, encoding="utf-8")

    with zipfile.ZipFile(staging / "reproducibility_bundle.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "assets/fonts").glob("*")):
            archive.write(path, f"fonts/{path.name}")
        for name in (
            "render.py",
            "build_dataset.py",
            "validate_fonts.py",
            "source_data.py",
            "ocr_metrics.py",
        ):
            archive.write(ROOT / name, name)

    print(
        f"Staged {len(output_rows)} benchmark images, {len(canary_rows)} canaries, "
        f"and {len(contact_sheets)} contact sheets in {staging}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("assets/full/manifest.jsonl"))
    parser.add_argument("--staging", type=Path, default=Path("kaggle_dataset_full"))
    parser.add_argument(
        "--sources", type=Path, default=Path("assets/full/source/urdu_wikipedia.json")
    )
    parser.add_argument(
        "--summary", type=Path, default=Path("assets/full/dataset_summary.json")
    )
    parser.add_argument(
        "--validation", type=Path, default=Path("results/full/offline_validation.json")
    )
    parser.add_argument(
        "--contact-sheet",
        type=Path,
        default=Path("assets/full/contact_sheets/full_contact_sheet.png"),
    )
    parser.add_argument("--dataset-ref", default="huzaifa12344/urdu-font-twin-60")
    args = parser.parse_args()
    build_package(
        args.manifest,
        args.staging,
        args.sources,
        args.summary,
        args.validation,
        args.contact_sheet,
        args.dataset_ref,
    )


if __name__ == "__main__":
    main()
