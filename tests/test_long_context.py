from __future__ import annotations

import pytest

from ism.data.generator import GeneratedDocument, SyntheticGenerator


def _short() -> tuple[GeneratedDocument, ...]:
    return SyntheticGenerator(42).generate(5, split="dev")


def _long() -> tuple[GeneratedDocument, ...]:
    return SyntheticGenerator(
        42, document_min_tokens=700, document_max_tokens=2000
    ).generate(5, split="dev")


def test_filler_is_deterministic() -> None:
    assert [d.document_text for d in _long()] == [d.document_text for d in _long()]


def test_filler_length_in_range() -> None:
    for document in _long():
        n = len(document.document_text.split())
        assert 700 <= n <= 2000


def test_filler_preserves_graph_questions_and_answers() -> None:
    for short, long in zip(_short(), _long(), strict=True):
        assert short.document_id == long.document_id
        assert short.graph == long.graph  # gold rule graph unchanged
        assert short.questions == long.questions  # questions + answers unchanged
        # The original rendered document is a prefix; filler only appends.
        assert long.document_text.startswith(short.document_text)


def test_long_full_context_mean_tokens_exceeds_max_budget() -> None:
    docs = _long()
    mean = sum(len(d.document_text.split()) for d in docs) / len(docs)
    assert mean > 512  # so budgets up to 512 are genuine compression


def test_generator_rejects_half_set_document_length() -> None:
    with pytest.raises(ValueError, match="must be set together"):
        SyntheticGenerator(42, document_min_tokens=700)
    with pytest.raises(ValueError, match="must not exceed"):
        SyntheticGenerator(42, document_min_tokens=2000, document_max_tokens=700)
