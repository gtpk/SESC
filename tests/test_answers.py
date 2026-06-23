from __future__ import annotations

from pathlib import Path

from ism.evaluation.answers import answers_match, normalize_answer
from ism.inference.artifacts import AtomicPredictionStore
from ism.inference.contracts import GenerationRequest, GenerationResult
from ism.inference.pipeline import build_qa_prompt
from ism.inference.runner import InferenceRunner, InferenceSample


class _FixedGenerator:
    def __init__(self, text: str) -> None:
        self._text = text

    def generate(
        self, requests: tuple[GenerationRequest, ...]
    ) -> tuple[GenerationResult, ...]:
        return tuple(
            GenerationResult(
                request_id=request.request_id,
                text=self._text,
                input_tokens=1,
                output_tokens=1,
            )
            for request in requests
        )


def test_normalize_answer_is_case_and_punctuation_insensitive() -> None:
    assert normalize_answer("  HIGH. ") == "high"
    assert normalize_answer("**Low**") == "low"


def test_normalize_answer_maps_boolean_synonyms() -> None:
    assert normalize_answer("True") == "true"
    assert normalize_answer("yes") == "true"
    assert normalize_answer("No.") == "false"


def test_answers_match_handles_format_drift() -> None:
    assert answers_match("HIGH", "high")
    assert answers_match("Yes", "True")
    assert not answers_match("HIGH", "LOW")


def test_build_qa_prompt_constrains_answer_format() -> None:
    classification = build_qa_prompt(
        context="ctx", question="What is the risk level?", answer_type="classification"
    )
    boolean = build_qa_prompt(
        context="ctx", question="Does it require review?", answer_type="boolean"
    )

    assert "single word" in classification
    assert "True or False" in boolean
    assert "Context:\nctx" in classification


def test_runner_scores_answers_case_insensitively(tmp_path: Path) -> None:
    sample = InferenceSample(
        sample_id="s",
        question_id="q",
        condition="full_context",
        prompt="p",
        expected_output="HIGH",
    )
    records = InferenceRunner(
        _FixedGenerator("  high. "),
        AtomicPredictionStore(tmp_path / "predictions.jsonl"),
        max_new_tokens=8,
        seed=1,
    ).run((sample,), batch_size=1, max_attempts=1)

    assert records[0].correct is True
    assert records[0].prediction_normalized == "high."
