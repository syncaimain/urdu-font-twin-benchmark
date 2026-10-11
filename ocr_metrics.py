"""Unicode-conscious OCR metrics for Urdu transcription."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Sequence, TypeVar


T = TypeVar("T")
URDU_WORD_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]+")


def normalize_urdu(text: str) -> str:
    """NFC plus whitespace cleanup; never folds distinct Urdu/Arabic letters."""
    text = unicodedata.normalize("NFC", str(text))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return " ".join(text.strip().split())


@dataclass(frozen=True)
class EditCounts:
    insertions: int
    deletions: int
    substitutions: int
    correct: int

    @property
    def errors(self) -> int:
        return self.insertions + self.deletions + self.substitutions


def edit_counts(reference: Sequence[T], hypothesis: Sequence[T]) -> EditCounts:
    rows, cols = len(reference) + 1, len(hypothesis) + 1
    table: list[list[tuple[int, int, int, int]]] = [[(0, 0, 0, 0) for _ in range(cols)] for _ in range(rows)]
    for i in range(1, rows):
        table[i][0] = (i, 0, 0, 0)
    for j in range(1, cols):
        table[0][j] = (0, j, 0, 0)
    for i in range(1, rows):
        for j in range(1, cols):
            if reference[i - 1] == hypothesis[j - 1]:
                d, ins, sub, cor = table[i - 1][j - 1]
                table[i][j] = (d, ins, sub, cor + 1)
                continue
            d0, i0, s0, c0 = table[i - 1][j]
            deletion = (d0 + 1, i0, s0, c0)
            d0, i0, s0, c0 = table[i][j - 1]
            insertion = (d0, i0 + 1, s0, c0)
            d0, i0, s0, c0 = table[i - 1][j - 1]
            substitution = (d0, i0, s0 + 1, c0)
            table[i][j] = min((deletion, insertion, substitution), key=lambda value: (sum(value[:3]), value[2], value[0]))
    deletions, insertions, substitutions, correct = table[-1][-1]
    return EditCounts(insertions, deletions, substitutions, correct)


def score_text(reference: str, hypothesis: str) -> dict:
    ref = normalize_urdu(reference)
    hyp = normalize_urdu(hypothesis)
    char_edits = edit_counts(list(ref), list(hyp))
    ref_words, hyp_words = ref.split(), hyp.split()
    word_edits = edit_counts(ref_words, hyp_words)
    return {
        "reference_normalized": ref,
        "hypothesis_normalized": hyp,
        "cer": char_edits.errors / max(1, len(ref)),
        "wer": word_edits.errors / max(1, len(ref_words)),
        "char_insertions": char_edits.insertions,
        "char_deletions": char_edits.deletions,
        "char_substitutions": char_edits.substitutions,
        "word_insertions": word_edits.insertions,
        "word_deletions": word_edits.deletions,
        "word_substitutions": word_edits.substitutions,
    }


def urdu_words(text: str) -> list[str]:
    return URDU_WORD_RE.findall(normalize_urdu(text))


def real_word_hallucinations(reference: str, hypothesis: str, lexicon: set[str]) -> dict:
    reference_words = set(urdu_words(reference))
    predicted = urdu_words(hypothesis)
    hits = [word for word in predicted if word in lexicon and word not in reference_words]
    return {
        "real_word_hallucination_count": len(hits),
        "real_word_hallucination_rate": len(hits) / max(1, len(predicted)),
        "real_word_hallucinations": hits,
    }
