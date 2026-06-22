from __future__ import annotations

from collections import Counter

from ism.inference.contracts import (
    ErrorKind,
    GenerationRequest,
    GenerationResult,
)


class MockTextGenerator:
    def __init__(
        self,
        *,
        name: str = "mock",
        failure_plan: dict[str, tuple[ErrorKind, ...]] | None = None,
    ) -> None:
        self.name = name
        self.failure_plan = failure_plan or {}
        self.attempts: Counter[str] = Counter()
        self.calls = 0

    def generate(
        self,
        requests: tuple[GenerationRequest, ...],
    ) -> tuple[GenerationResult, ...]:
        self.calls += 1
        results: list[GenerationResult] = []
        for request in requests:
            attempt = self.attempts[request.request_id]
            self.attempts[request.request_id] += 1
            failures = self.failure_plan.get(request.request_id, ())
            if attempt < len(failures):
                kind = failures[attempt]
                results.append(
                    GenerationResult(
                        request_id=request.request_id,
                        error_kind=kind,
                        error_message=f"{self.name} planned {kind.value} failure",
                    )
                )
                continue
            text = request.expected_output
            if text is None:
                text = f"{self.name}:{request.request_id}"
            results.append(
                GenerationResult(
                    request_id=request.request_id,
                    text=text,
                    input_tokens=len(request.prompt.split()),
                    output_tokens=len(text.split()),
                    latency_ms=0,
                )
            )
        return tuple(results)
