from __future__ import annotations

from collections.abc import Iterable

from ism.evaluation.answers import answers_match
from ism.inference.artifacts import AtomicPredictionStore
from ism.inference.contracts import (
    ErrorKind,
    GenerationRequest,
    GenerationResult,
    TextGenerator,
)
from ism.inference.runner_models import InferenceSample, PredictionRecord


class PipelineInterrupted(RuntimeError):
    pass


class InferenceRunner:
    def __init__(
        self,
        generator: TextGenerator,
        store: AtomicPredictionStore,
        *,
        max_new_tokens: int,
        seed: int,
    ) -> None:
        self.generator = generator
        self.store = store
        self.max_new_tokens = max_new_tokens
        self.seed = seed

    def run(
        self,
        samples: Iterable[InferenceSample],
        *,
        batch_size: int,
        max_attempts: int,
        resume: bool = False,
        stop_after: int | None = None,
    ) -> tuple[PredictionRecord, ...]:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        ordered = tuple(samples)
        if len({sample.key for sample in ordered}) != len(ordered):
            raise ValueError("samples contain duplicate sample-condition keys")
        if len({sample.sample_id for sample in ordered}) != len(ordered):
            raise ValueError("sample IDs must be unique adapter request IDs")

        existing = self.store.load()
        if existing and not resume:
            raise ValueError("prediction artifact exists; use resume=True")
        completed = {record.key for record in existing}
        pending = [sample for sample in ordered if sample.key not in completed]
        written = 0

        for start in range(0, len(pending), batch_size):
            batch = pending[start : start + batch_size]
            records = self._run_batch(batch, max_attempts=max_attempts)
            self.store.append(records)
            written += len(records)
            if stop_after is not None and written >= stop_after:
                raise PipelineInterrupted(f"stopped after {written} new records")

        by_key = {record.key: record for record in self.store.load()}
        return tuple(by_key[sample.key] for sample in ordered)

    def _run_batch(
        self,
        samples: list[InferenceSample],
        *,
        max_attempts: int,
    ) -> tuple[PredictionRecord, ...]:
        requests = {
            sample.sample_id: GenerationRequest(
                request_id=sample.sample_id,
                prompt=sample.prompt,
                max_new_tokens=self.max_new_tokens,
                seed=self.seed,
                expected_output=sample.expected_output,
            )
            for sample in samples
        }
        unresolved = dict(requests)
        final: dict[str, GenerationResult] = {}
        attempts = {request_id: 0 for request_id in requests}

        for _ in range(max_attempts):
            if not unresolved:
                break
            current = tuple(unresolved.values())
            generated = self.generator.generate(current)
            self._validate_adapter_results(current, generated)
            unresolved = {}
            for result in generated:
                attempts[result.request_id] += 1
                if (
                    result.error_kind is ErrorKind.TRANSIENT
                    and attempts[result.request_id] < max_attempts
                ):
                    unresolved[result.request_id] = requests[result.request_id]
                else:
                    final[result.request_id] = result

        records: list[PredictionRecord] = []
        samples_by_id = {sample.sample_id: sample for sample in samples}
        for request_id in requests:
            result = final[request_id]
            sample = samples_by_id[request_id]
            normalized = result.text.strip() if result.text is not None else None
            correct = normalized is not None and answers_match(
                normalized, sample.expected_output
            )
            records.append(
                PredictionRecord(
                    sample_id=sample.sample_id,
                    question_id=sample.question_id,
                    condition=sample.condition,
                    prediction_raw=result.text,
                    prediction_normalized=normalized,
                    expected_output=sample.expected_output,
                    correct=correct,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    latency_ms=result.latency_ms,
                    attempts=attempts[request_id],
                    error_kind=result.error_kind,
                    error_message=result.error_message,
                )
            )
        return tuple(records)

    def _validate_adapter_results(
        self,
        requests: tuple[GenerationRequest, ...],
        results: tuple[GenerationResult, ...],
    ) -> None:
        expected = {request.request_id for request in requests}
        received = [result.request_id for result in results]
        if len(received) != len(set(received)):
            raise ValueError("adapter returned duplicate request IDs")
        if set(received) != expected:
            raise ValueError("adapter result IDs do not match request IDs")


__all__ = ["InferenceRunner", "InferenceSample", "PipelineInterrupted", "PredictionRecord"]
