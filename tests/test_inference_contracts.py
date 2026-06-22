from __future__ import annotations

import pytest
from pydantic import ValidationError

from ism.inference.contracts import ErrorKind, GenerationResult
from ism.inference.errors import classify_exception


def test_p3_con_001_generation_result_success_and_failure_contract() -> None:
    success = GenerationResult(request_id="ok", text="HIGH")
    failure = GenerationResult(
        request_id="failed",
        error_kind=ErrorKind.TRANSIENT,
        error_message="timeout",
    )

    assert success.succeeded
    assert not failure.succeeded

    with pytest.raises(ValidationError, match="requires text"):
        GenerationResult(request_id="invalid")
    with pytest.raises(ValidationError, match="cannot contain text"):
        GenerationResult(
            request_id="invalid",
            text="partial",
            error_kind=ErrorKind.FATAL,
            error_message="failed",
        )


def test_p3_err_001_oom_is_not_classified_as_parser_or_validation_error() -> None:
    assert classify_exception(MemoryError("CUDA out of memory")) is ErrorKind.OUT_OF_MEMORY
    assert classify_exception(RuntimeError("CUDA OOM")) is ErrorKind.OUT_OF_MEMORY
    assert classify_exception(ValueError("bad parser output")) is ErrorKind.VALIDATION
