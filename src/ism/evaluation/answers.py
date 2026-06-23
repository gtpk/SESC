from __future__ import annotations

# Surrounding characters stripped before comparison (markdown emphasis, quotes,
# brackets, trailing punctuation a model tends to add around a short answer).
_WRAPPING = ".,!?:;\"'`*()[]{}<> \n\t"

# Boolean answers are generated as ``str(bool)`` ("True"/"False"); accept the
# natural-language equivalents a model may emit.
_BOOLEAN_SYNONYMS = {
    "true": "true",
    "yes": "true",
    "false": "false",
    "no": "false",
}


def normalize_answer(text: str) -> str:
    """Canonicalize a short answer for exact-match scoring.

    Case-insensitive, whitespace-collapsed, and stripped of wrapping
    punctuation. Boolean-style answers are mapped to a canonical true/false so
    that "Yes", "true.", and "TRUE" all compare equal to the generated "True".
    """
    cleaned = " ".join(text.casefold().split()).strip(_WRAPPING)
    return _BOOLEAN_SYNONYMS.get(cleaned, cleaned)


def answers_match(prediction: str, expected: str) -> bool:
    return normalize_answer(prediction) == normalize_answer(expected)


__all__ = ["answers_match", "normalize_answer"]
