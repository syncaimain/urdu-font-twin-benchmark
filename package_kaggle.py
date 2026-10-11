"""Build the flat private Kaggle dataset upload directory."""

from __future__ import annotations

import csv
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STAGING = ROOT / "kaggle_dataset"


def build_package() -> None:
    rows = [
        json.loads(line)
        for line in (ROOT / "assets/manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    output_rows = []
    for row in rows:
        source = ROOT / row["image_path"]
        image_file = source.name
        shutil.copy2(source, STAGING / image_file)
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
    with (STAGING / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    canaries = json.loads((ROOT / "assets/canaries/manifest.json").read_text(encoding="utf-8"))
    canary_rows = []
    for row in canaries:
        source = ROOT / row["image_path"]
        image_file = f"canary_{source.name}"
        shutil.copy2(source, STAGING / image_file)
        canary_rows.append(
            {"canary_id": row["canary_id"], "expected": row["expected"], "image_file": image_file}
        )
    with (STAGING / "canaries.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["canary_id", "expected", "image_file"])
        writer.writeheader()
        writer.writerows(canary_rows)

    copies = {
        ROOT / "kaggle_task.py": "kaggle_task.py",
        ROOT / "assets/contact_sheets/pilot_contact_sheet.png": "pilot_contact_sheet.png",
        ROOT / "assets/dataset_summary.json": "dataset_summary.json",
        ROOT / "assets/font_calibration.json": "font_calibration.json",
        ROOT / "results/offline_validation.json": "offline_validation.json",
        ROOT / "assets/source/urdu_wikipedia.json": "urdu_wikipedia_sources.json",
    }
    for source, target in copies.items():
        shutil.copy2(source, STAGING / target)

    with zipfile.ZipFile(STAGING / "reproducibility_bundle.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "assets/fonts").glob("*")):
            archive.write(path, f"fonts/{path.name}")
        for name in ("render.py", "build_dataset.py", "validate_fonts.py", "source_data.py", "ocr_metrics.py"):
            archive.write(ROOT / name, name)

    print(f"Staged {len(output_rows)} benchmark images and {len(canary_rows)} canaries in {STAGING}")


if __name__ == "__main__":
    build_package()
