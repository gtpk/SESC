"""Model-independent inference contracts and execution."""

from ism.inference.contracts import (
    ErrorKind,
    GenerationRequest,
    GenerationResult,
    TextGenerator,
)
from ism.inference.mock import MockTextGenerator
from ism.inference.runner import InferenceRunner, InferenceSample, PredictionRecord

__all__ = [
    "ErrorKind",
    "GenerationRequest",
    "GenerationResult",
    "InferenceRunner",
    "InferenceSample",
    "MockTextGenerator",
    "PredictionRecord",
    "TextGenerator",
]
