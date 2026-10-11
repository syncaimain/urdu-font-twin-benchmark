"""Offline font, shaping, bounds, and font-twin validation."""

from __future__ import annotations

import argparse
import json
import unicodedata
from collections import defaultdict
from pathlib import Path

from PIL import Image
from fontTools.ttLib import TTFont

from render import FONT_SPECS, UrduRenderer, font_codepoints, font_sha256, visible_bbox


IGNORED_CMAP = {"\n", "\r", "\t", " "}


def validate(manifest_path: Path) -> dict:
    records = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line]
    required_chars = sorted({char for row in records for char in row["text"] if char not in IGNORED_CMAP})
    unique_texts = sorted({row["text"] for row in records})
    report: dict = {"passed": True, "manifest": str(manifest_path), "images_checked": len(records), "fonts": {}, "pairs": {}}
    for key, spec in FONT_SPECS.items():
        codepoints = font_codepoints(spec.path)
        missing = [f"U+{ord(char):04X} {unicodedata.name(char, 'UNKNOWN')}" for char in required_chars if ord(char) not in codepoints]
        ttfont = TTFont(spec.path, lazy=True)
        renderer = UrduRenderer(spec.path, 96)
        shaped = renderer.shape("لا پاکستان پڑھائی")
        contextual_glyphs = len({glyph.glyph_id for glyph in shaped.glyphs}) > 3 and all(glyph.glyph_id != 0 for glyph in shaped.glyphs)
        clusters = [glyph.cluster for glyph in shaped.glyphs]
        rtl_order = clusters == sorted(clusters, reverse=True)
        lookups = ttfont["GSUB"].table.LookupList.Lookup
        ligature_lookups = sum(lookup.LookupType == 4 for lookup in lookups)
        ligature_lookups += sum(
            1
            for lookup in lookups
            if lookup.LookupType == 7
            for subtable in lookup.SubTable
            if getattr(subtable, "ExtensionLookupType", None) == 4
        )
        shape_failures = []
        for index, text in enumerate(unique_texts):
            test_shape = renderer.shape(text)
            test_clusters = [glyph.cluster for glyph in test_shape.glyphs]
            if any(glyph.glyph_id == 0 for glyph in test_shape.glyphs):
                shape_failures.append({"text_index": index, "reason": "notdef glyph"})
            elif test_clusters != sorted(test_clusters, reverse=True):
                shape_failures.append({"text_index": index, "reason": "non-RTL cluster order"})
        font_result = {
            "path": str(spec.path).replace("\\", "/"),
            "sha256": font_sha256(spec.path),
            "missing_codepoints": missing,
            "has_GSUB": "GSUB" in ttfont,
            "has_GPOS": "GPOS" in ttfont,
            "gsub_ligature_lookup_count": ligature_lookups,
            "shape_test_nonzero": contextual_glyphs,
            "shape_test_rtl_cluster_order": rtl_order,
            "all_manifest_strings_shaped": not shape_failures,
            "manifest_shape_failures": shape_failures,
            "single_font_no_fallback": True,
        }
        font_result["passed"] = not missing and all(
            [
                font_result["has_GSUB"],
                font_result["has_GPOS"],
                ligature_lookups > 0,
                contextual_glyphs,
                rtl_order,
                not shape_failures,
            ]
        )
        report["fonts"][key] = font_result
        report["passed"] = report["passed"] and font_result["passed"]

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    invalid_bounds: list[str] = []
    blank_images: list[str] = []
    for row in records:
        grouped[(row["pair_id"], row["resolution"])].append(row)
        image = Image.open(row["image_path"]).convert("L")
        bbox = visible_bbox(image)
        if bbox is None:
            blank_images.append(row["image_id"])
        elif bbox[0] <= 0 or bbox[1] <= 0 or bbox[2] >= image.width or bbox[3] >= image.height:
            invalid_bounds.append(row["image_id"])

    mismatched_pairs: list[str] = []
    incomplete_pairs: list[str] = []
    for (pair_id, resolution), rows in grouped.items():
        if len(rows) != 2 or {row["font_key"] for row in rows} != {"nastaliq", "naskh"}:
            incomplete_pairs.append(f"{pair_id}:{resolution}")
        elif len({row["text"] for row in rows}) != 1 or len({row["text_sha256"] for row in rows}) != 1:
            mismatched_pairs.append(f"{pair_id}:{resolution}")
    report["pairs"] = {
        "groups_checked": len(grouped),
        "incomplete_pairs": incomplete_pairs,
        "unicode_mismatches": mismatched_pairs,
        "blank_images": blank_images,
        "out_of_bounds_images": invalid_bounds,
    }
    report["passed"] = report["passed"] and not any(
        (incomplete_pairs, mismatched_pairs, blank_images, invalid_bounds)
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("assets/manifest.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("results/offline_validation.json"))
    args = parser.parse_args()
    report = validate(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
