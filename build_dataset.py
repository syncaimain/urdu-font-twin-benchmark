"""Build the deterministic Urdu Nastaliq/Naskh font-twin pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import unicodedata
from pathlib import Path

from PIL import Image

from render import FONT_SPECS, UrduRenderer, calibration_report, create_contact_sheet, visible_bbox


CONDITIONS = ("natural", "shuffled", "pseudo")
PSEUDO_ALPHABET = "ابتپٹجچدڈرزژسشصضطظعغفقکگلمنںوہھیے"
URDU_LETTER_RE = re.compile(r"[\u0621-\u063a\u0641-\u064a\u066e-\u06d3\u06fa-\u06ff]")


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_source_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.translate(str.maketrans({"?": "؟", ",": "،", ";": "؛"}))
    text = re.sub(r"[\u200b\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", text)
    return " ".join(text.split())


def shuffled_text(text: str, seed_key: str) -> str:
    words = text.split()
    rng = random.Random(int(stable_hash(seed_key)[:16], 16))
    shuffled = words[:]
    rng.shuffle(shuffled)
    if shuffled == words and len(words) > 1:
        shuffled = shuffled[1:] + shuffled[:1]
    return " ".join(shuffled)


def pseudo_text(text: str, seed_key: str, real_words: set[str]) -> str:
    output: list[str] = []
    for word_index, word in enumerate(text.split()):
        attempt = 0
        while True:
            characters: list[str] = []
            for char_index, char in enumerate(word):
                if URDU_LETTER_RE.fullmatch(char):
                    digest = stable_hash(f"{seed_key}:{word_index}:{char_index}:{attempt}")
                    characters.append(PSEUDO_ALPHABET[int(digest[:8], 16) % len(PSEUDO_ALPHABET)])
                else:
                    characters.append(char)
            candidate = "".join(characters)
            bare = "".join(URDU_LETTER_RE.findall(candidate))
            if bare not in real_words or attempt >= 20:
                output.append(candidate)
                break
            attempt += 1
    return " ".join(output)


def condition_texts(source: dict, real_words: set[str]) -> dict[str, str]:
    natural = clean_source_text(source["text"])
    return {
        "natural": natural,
        "shuffled": shuffled_text(natural, source["source_id"]),
        "pseudo": pseudo_text(natural, source["source_id"], real_words),
    }


def _save_resolution(image: Image.Image, path: Path, scale: float) -> Image.Image:
    if scale != 1.0:
        size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        image = image.resize(size, Image.Resampling.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
    return image


def build_dataset(
    source_path: Path,
    output_dir: Path,
    manifest_path: Path,
    limit: int = 15,
    resolution_scales: tuple[float, ...] = (1.0,),
) -> list[dict]:
    sources = json.loads(source_path.read_text(encoding="utf-8"))[:limit]
    if len(sources) < limit:
        raise ValueError(f"Requested {limit} source items but only {len(sources)} are available")
    real_words = {
        "".join(URDU_LETTER_RE.findall(word))
        for source in sources
        for word in clean_source_text(source["text"]).split()
    }
    calibration = calibration_report()
    renderers = {
        key: UrduRenderer(spec.path, calibration["fonts"][key]["pixel_size"])
        for key, spec in FONT_SPECS.items()
    }
    records: list[dict] = []
    for source_index, source in enumerate(sources, start=1):
        for condition, text in condition_texts(source, real_words).items():
            pair_id = f"p{source_index:02d}-{condition}"
            text_hash = stable_hash(text)
            for font_key, spec in FONT_SPECS.items():
                canonical = renderers[font_key].render(text)
                for scale in resolution_scales:
                    resolution = "canonical" if scale == 1.0 else f"scale-{scale:g}"
                    image_id = f"{pair_id}-{font_key}-{resolution}"
                    relative_path = output_dir / resolution / f"{image_id}.png"
                    image = _save_resolution(canonical, relative_path, scale)
                    bbox = visible_bbox(image)
                    records.append(
                        {
                            "image_id": image_id,
                            "pair_id": pair_id,
                            "source_id": source["source_id"],
                            "condition": condition,
                            "text": text,
                            "text_sha256": text_hash,
                            "font_key": font_key,
                            "font_name": spec.label,
                            "font_path": str(spec.path).replace("\\", "/"),
                            "font_sha256": calibration["fonts"][font_key]["sha256"],
                            "font_pixel_size": calibration["fonts"][font_key]["pixel_size"],
                            "resolution": resolution,
                            "resolution_scale": scale,
                            "width": image.width,
                            "height": image.height,
                            "visible_bbox": list(bbox) if bbox else None,
                            "image_path": str(relative_path).replace("\\", "/"),
                            "source_url": source["source_url"],
                            "source_revision_url": source["revision_url"],
                            "source_revision_id": source["revision_id"],
                            "source_license": source["license"],
                            "source_license_url": source["license_url"],
                        }
                    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8"
    )
    create_contact_sheet(records, Path("assets/contact_sheets/pilot_contact_sheet.png"))
    _build_canaries(renderers)
    summary = {
        "source_items": len(sources),
        "conditions": list(CONDITIONS),
        "font_pairs": len(sources) * len(CONDITIONS),
        "images": len(records),
        "resolution_scales": list(resolution_scales),
        "normalization": "Unicode NFC; whitespace collapsed; distinct Urdu letters are never folded",
        "source": "Urdu Wikipedia revision-pinned excerpts, CC BY-SA 4.0",
    }
    Path("assets/dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return records


def _build_canaries(renderers: dict[str, UrduRenderer]) -> None:
    items = [
        ("number", "5831", "naskh", {"direction": "ltr", "script": "Latn", "language": "en"}),
        ("urdu_word", "کتاب", "nastaliq", {}),
    ]
    rows = []
    for canary_id, text, font_key, shaping in items:
        image = renderers[font_key].render(text, **shaping)
        path = Path("assets/canaries") / f"{canary_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, optimize=True)
        rows.append(
            {
                "canary_id": canary_id,
                "expected": text,
                "font_key": font_key,
                "direction": shaping.get("direction", "rtl"),
                "image_path": str(path).replace("\\", "/"),
            }
        )
    Path("assets/canaries/manifest.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("assets/source/urdu_wikipedia.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("assets/images"))
    parser.add_argument("--manifest", type=Path, default=Path("assets/manifest.jsonl"))
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--resolution-scales", type=float, nargs="+", default=[1.0])
    args = parser.parse_args()
    records = build_dataset(args.source, args.output_dir, args.manifest, args.limit, tuple(args.resolution_scales))
    print(f"Built {len(records)} images ({len(records) // 2} font pairs) and {args.manifest}")


if __name__ == "__main__":
    main()
