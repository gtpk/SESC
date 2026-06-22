from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from ism.inference.contracts import ErrorKind


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InferenceSample(FrozenModel):
    sample_id: Annotated[str, Field(min_length=1)]
    question_id: Annotated[str, Field(min_length=1)]
    condition: Annotated[str, Field(min_length=1)]
    prompt: str
    expected_output: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.sample_id, self.condition)


class PredictionRecord(FrozenModel):
    sample_id: str
    question_id: str
    condition: str
    prediction_raw: str | None
    prediction_normalized: str | None
    expected_output: str
    correct: bool
    input_tokens: int
    output_tokens: int
    latency_ms: float
    attempts: int
    error_kind: ErrorKind | None = None
    error_message: str | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.sample_id, self.condition)
