from __future__ import annotations

from pathlib import Path

import pytest

from ism.inference.artifacts import AtomicPredictionStore
from ism.inference.contracts import ErrorKind
from ism.inference.mock import MockTextGenerator
from ism.inference.runner import (
    InferenceRunner,
    InferenceSample,
    PipelineInterrupted,
)
from ism.inference.runner_models import PredictionRecord


def samples(count: int = 4) -> tuple[InferenceSample, ...]:
    return tuple(
        InferenceSample(
            sample_id=f"sample-{index}",
            question_id=f"question-{index}",
            condition="full_context",
            prompt=f"prompt {index}",
            expected_output=f"answer-{index}",
        )
        for index in range(count)
    )


def runner(
    path: Path,
    generator: MockTextGenerator,
) -> InferenceRunner:
    return InferenceRunner(
        generator,
        AtomicPredictionStore(path),
        max_new_tokens=16,
        seed=42,
    )


def test_p3_arc_001_runner_accepts_substitutable_adapters(tmp_path: Path) -> None:
    first = runner(tmp_path / "a.jsonl", MockTextGenerator(name="a")).run(
        samples(2),
        batch_size=2,
        max_attempts=1,
    )
    second = runner(tmp_path / "b.jsonl", MockTextGenerator(name="b")).run(
        samples(2),
        batch_size=2,
        max_attempts=1,
    )

    assert [item.prediction_raw for item in first] == ["answer-0", "answer-1"]
    assert [item.prediction_raw for item in second] == ["answer-0", "answer-1"]


def test_p3_int_002_batch_size_preserves_results_and_order(tmp_path: Path) -> None:
    one = runner(tmp_path / "one.jsonl", MockTextGenerator()).run(
        samples(),
        batch_size=1,
        max_attempts=1,
    )
    many = runner(tmp_path / "many.jsonl", MockTextGenerator()).run(
        samples(),
        batch_size=4,
        max_attempts=1,
    )

    assert one == many


def test_p3_res_001_interruption_leaves_only_complete_records(tmp_path: Path) -> None:
    path = tmp_path / "predictions.jsonl"

    with pytest.raises(PipelineInterrupted, match="stopped"):
        runner(path, MockTextGenerator()).run(
            samples(),
            batch_size=1,
            max_attempts=1,
            stop_after=2,
        )

    restored = AtomicPredictionStore(path).load()
    assert len(restored) == 2
    assert [item.sample_id for item in restored] == ["sample-0", "sample-1"]


def test_p3_res_002_resume_skips_completed_samples(tmp_path: Path) -> None:
    path = tmp_path / "predictions.jsonl"
    first_generator = MockTextGenerator()
    with pytest.raises(PipelineInterrupted):
        runner(path, first_generator).run(
            samples(),
            batch_size=1,
            max_attempts=1,
            stop_after=2,
        )

    resumed_generator = MockTextGenerator()
    records = runner(path, resumed_generator).run(
        samples(),
        batch_size=2,
        max_attempts=1,
        resume=True,
    )

    assert len(records) == 4
    assert sum(resumed_generator.attempts.values()) == 2

    no_op_generator = MockTextGenerator()
    rerun = runner(path, no_op_generator).run(
        samples(),
        batch_size=4,
        max_attempts=1,
        resume=True,
    )
    assert rerun == records
    assert no_op_generator.calls == 0


def test_p3_res_003_transient_failure_retries_then_succeeds(tmp_path: Path) -> None:
    generator = MockTextGenerator(
        failure_plan={"sample-0": (ErrorKind.TRANSIENT,)},
    )

    records = runner(tmp_path / "retry.jsonl", generator).run(
        samples(1),
        batch_size=1,
        max_attempts=2,
    )

    assert records[0].correct
    assert records[0].attempts == 2


def test_p3_res_004_retry_exhaustion_saves_failure(tmp_path: Path) -> None:
    generator = MockTextGenerator(
        failure_plan={
            "sample-0": (ErrorKind.TRANSIENT, ErrorKind.TRANSIENT),
        },
    )

    records = runner(tmp_path / "exhausted.jsonl", generator).run(
        samples(1),
        batch_size=1,
        max_attempts=2,
    )

    assert records[0].error_kind is ErrorKind.TRANSIENT
    assert records[0].attempts == 2
    assert not records[0].correct


def test_p3_err_002_partial_batch_failure_is_isolated(tmp_path: Path) -> None:
    generator = MockTextGenerator(
        failure_plan={"sample-1": (ErrorKind.OUT_OF_MEMORY,)},
    )

    records = runner(tmp_path / "partial.jsonl", generator).run(
        samples(3),
        batch_size=3,
        max_attempts=2,
    )

    assert records[0].correct
    assert records[1].error_kind is ErrorKind.OUT_OF_MEMORY
    assert records[2].correct


def test_p3_io_001_failed_atomic_replace_preserves_previous_file(tmp_path: Path) -> None:
    path = tmp_path / "atomic.jsonl"
    store = AtomicPredictionStore(path)
    initial = PredictionRecord(
        sample_id="sample-0",
        question_id="question-0",
        condition="full_context",
        prediction_raw="HIGH",
        prediction_normalized="HIGH",
        expected_output="HIGH",
        correct=True,
        input_tokens=1,
        output_tokens=1,
        latency_ms=0,
        attempts=1,
    )
    store.append((initial,))
    original = path.read_bytes()

    def interrupt(_: Path) -> None:
        raise RuntimeError("simulated interruption")

    failing = AtomicPredictionStore(path, before_replace=interrupt)
    with pytest.raises(RuntimeError, match="simulated"):
        failing.append(
            (initial.model_copy(update={"sample_id": "sample-1", "question_id": "question-1"}),)
        )

    assert path.read_bytes() == original
    assert store.load() == (initial,)


def test_p3_io_002_duplicate_prediction_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.jsonl"
    store = AtomicPredictionStore(path)
    record = PredictionRecord(
        sample_id="sample-0",
        question_id="question-0",
        condition="full_context",
        prediction_raw="HIGH",
        prediction_normalized="HIGH",
        expected_output="HIGH",
        correct=True,
        input_tokens=1,
        output_tokens=1,
        latency_ms=0,
        attempts=1,
    )
    store.append((record,))

    with pytest.raises(ValueError, match="already exist"):
        store.append((record,))


def test_runner_rejects_request_id_collision_across_conditions(tmp_path: Path) -> None:
    colliding = (
        InferenceSample(
            sample_id="same",
            question_id="question",
            condition="full_context",
            prompt="one",
            expected_output="HIGH",
        ),
        InferenceSample(
            sample_id="same",
            question_id="question",
            condition="symbol_only",
            prompt="two",
            expected_output="HIGH",
        ),
    )

    with pytest.raises(ValueError, match="request IDs"):
        runner(tmp_path / "collision.jsonl", MockTextGenerator()).run(
            colliding,
            batch_size=2,
            max_attempts=1,
        )
