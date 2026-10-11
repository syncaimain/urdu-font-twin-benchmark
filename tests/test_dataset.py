import json
from pathlib import Path

from build_dataset import condition_texts


def test_conditions_are_deterministic_and_separate():
    source = {"source_id": "x", "text": "پاکستان ایک خوبصورت ملک ہے۔"}
    first = condition_texts(source, {"پاکستان", "ایک", "خوبصورت", "ملک", "ہے"})
    second = condition_texts(source, {"پاکستان", "ایک", "خوبصورت", "ملک", "ہے"})
    assert first == second
    assert set(first) == {"natural", "shuffled", "pseudo"}
    assert first["natural"] != first["shuffled"]
    assert first["natural"] != first["pseudo"]


def test_generated_manifest_has_exact_font_twins():
    path = Path("assets/manifest.jsonl")
    if not path.exists():
        return
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    pairs = {}
    for row in rows:
        pairs.setdefault((row["pair_id"], row["resolution"]), []).append(row)
    assert len(pairs) == 45
    for pair in pairs.values():
        assert {row["font_key"] for row in pair} == {"nastaliq", "naskh"}
        assert len({row["text"] for row in pair}) == 1
        assert len({row["text_sha256"] for row in pair}) == 1
