from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ErrorKind(StrEnum):
    TRANSIENT = "transient"
    OUT_OF_MEMORY = "out_of_memory"
    VALIDATION = "validation"
    FATAL = "fatal"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GenerationRequest(FrozenModel):
    request_id: Annotated[str, Field(min_length=1)]
    prompt: str
    max_new_tokens: Annotated[int, Field(gt=0)]
    seed: int
    expected_output: str | None = None


class GenerationResult(FrozenModel):
    request_id: Annotated[str, Field(min_length=1)]
    text: str | None = None
    input_tokens: Annotated[int, Field(ge=0)] = 0
    output_tokens: Annotated[int, Field(ge=0)] = 0
    latency_ms: Annotated[float, Field(ge=0)] = 0
    error_kind: ErrorKind | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> GenerationResult:
        if self.error_kind is None:
            if self.text is None:
                raise ValueError("successful generation requires text")
            if self.error_message is not None:
                raise ValueError("successful generation cannot contain an error message")
        else:
            if self.text is not None:
                raise ValueError("failed generation cannot contain text")
            if not self.error_message:
                raise ValueError("failed generation requires an error message")
        return self

    @property
    def succeeded(self) -> bool:
        return self.error_kind is None


class TextGenerator(Protocol):
    def generate(
        self,
        requests: tuple[GenerationRequest, ...],
    ) -> tuple[GenerationResult, ...]: ...
