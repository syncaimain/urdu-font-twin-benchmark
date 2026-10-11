from ocr_metrics import edit_counts, normalize_urdu, score_text


def test_normalization_preserves_distinct_urdu_letters():
    assert normalize_urdu("ی ي ک ك ہ ھ") == "ی ي ک ك ہ ھ"


def test_edit_counts_known_example():
    counts = edit_counts(list("کتاب"), list("کباب"))
    assert counts.substitutions == 1
    assert counts.insertions == 0
    assert counts.deletions == 0


def test_cer_and_wer():
    result = score_text("ا ب", "ا پ")
    assert result["char_substitutions"] == 1
    assert result["word_substitutions"] == 1
    assert result["wer"] == 0.5
