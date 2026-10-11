from analysis import pseudo_hallucinations


def test_real_word_hallucinations_are_only_scored_for_pseudo_text():
    lexicon = {"پاکستان"}
    pseudo = pseudo_hallucinations("pseudo", "پاکسان", "پاکستان", lexicon)
    shuffled = pseudo_hallucinations("shuffled", "پاکسان", "پاکستان", lexicon)

    assert pseudo["real_word_hallucination_count"] == 1
    assert shuffled["real_word_hallucination_count"] == 0
    assert shuffled["real_word_hallucination_rate"] == 0.0
