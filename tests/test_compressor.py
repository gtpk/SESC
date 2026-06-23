from __future__ import annotations

import pytest

from ism.data.generator import SyntheticGenerator
from ism.experiments.compressor import (
    CompressionError,
    LlmCompressor,
    build_compression_prompt,
)
from ism.inference.contracts import GenerationRequest, GenerationResult
from ism.representation.tokenizer import WhitespaceTokenCounter

_VALID_ISM = (
    "[DICTIONARY]\n"
    "Z1 := IF condition a THEN risk = HIGH\n"
    "Z2 := IF condition b THEN review = true\n\n"
    "[RELATIONS]\n"
    "Z1 Z2\n"
)


class _ScriptedGenerator:
    """Returns a queued text per call (FIFO), echoing the request id."""

    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.calls = 0

    def generate(self, requests: tuple[GenerationRequest, ...]) -> tuple[GenerationResult, ...]:
        self.calls += 1
        text = self._texts.pop(0)
        return tuple(
            GenerationResult(request_id=r.request_id, text=text, input_tokens=1, output_tokens=1)
            for r in requests
        )


def _document():
    return SyntheticGenerator(42).generate(1, split="dev")[0]


def test_build_compression_prompt_has_format_and_budget() -> None:
    prompt = build_compression_prompt("doc text", budget=128)
    assert "[DICTIONARY]" in prompt
    assert "[RELATIONS]" in prompt
    assert "128" in prompt
    assert "doc text" in prompt
    assert "BOTH the trigger" in prompt
    assert "THEN risk = HIGH" in prompt


def test_compress_parses_valid_ism_on_first_attempt() -> None:
    generator = _ScriptedGenerator([_VALID_ISM])
    outcome = LlmCompressor(
        generator,
        tokenizer=WhitespaceTokenCounter(),
        seed=42,
        max_attempts=3,
        max_new_tokens=256,
    ).compress(_document(), budget=128)

    assert outcome.attempts == 1
    assert {d.label for d in outcome.representation.dictionary} == {"Z1", "Z2"}


def test_compress_regenerates_after_malformed_output() -> None:
    generator = _ScriptedGenerator(["not an ISM at all", _VALID_ISM])
    outcome = LlmCompressor(
        generator,
        tokenizer=WhitespaceTokenCounter(),
        seed=42,
        max_attempts=3,
        max_new_tokens=256,
    ).compress(_document(), budget=128)

    assert outcome.attempts == 2


def test_compress_regenerates_after_missing_conclusion_tokens() -> None:
    missing_conclusion = (
        "[DICTIONARY]\n"
        "Z1 := marker_a high and marker_b low\n"
        "Z2 := repair score above threshold\n\n"
        "[RELATIONS]\n"
        "Z1 Z2 => HIGH\n"
    )
    generator = _ScriptedGenerator([missing_conclusion, _VALID_ISM])
    outcome = LlmCompressor(
        generator,
        tokenizer=WhitespaceTokenCounter(),
        seed=42,
        max_attempts=3,
        max_new_tokens=256,
    ).compress(_document(), budget=128)

    assert outcome.attempts == 2


def test_compress_raises_when_every_attempt_lacks_conclusion_tokens() -> None:
    missing_conclusion = (
        "[DICTIONARY]\n"
        "Z1 := marker_a high and marker_b low\n"
        "Z2 := repair score above threshold\n\n"
        "[RELATIONS]\n"
        "Z1 Z2 => HIGH\n"
    )

    with pytest.raises(CompressionError, match="missing_conclusion_tokens"):
        LlmCompressor(
            _ScriptedGenerator([missing_conclusion, missing_conclusion]),
            tokenizer=WhitespaceTokenCounter(),
            seed=42,
            max_attempts=2,
            max_new_tokens=256,
        ).compress(_document(), budget=128)


def test_compress_raises_after_exhausting_attempts() -> None:
    generator = _ScriptedGenerator(["garbage", "still garbage"])
    with pytest.raises(CompressionError):
        LlmCompressor(
            generator,
            tokenizer=WhitespaceTokenCounter(),
            seed=42,
            max_attempts=2,
            max_new_tokens=256,
        ).compress(_document(), budget=128)


def test_compress_rejects_over_budget_output() -> None:
    big = "[DICTIONARY]\nZ1 := " + "word " * 200 + "\n\n[RELATIONS]\nZ1\n"
    generator = _ScriptedGenerator([big])
    with pytest.raises(CompressionError):
        LlmCompressor(
            generator,
            tokenizer=WhitespaceTokenCounter(),
            seed=42,
            max_attempts=1,
            max_new_tokens=512,
        ).compress(_document(), budget=128)
