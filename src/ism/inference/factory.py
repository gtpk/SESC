from __future__ import annotations

from ism.config import AppConfig
from ism.inference.contracts import TextGenerator
from ism.inference.mock import MockTextGenerator


def build_text_generator(config: AppConfig) -> TextGenerator:
    """Construct the configured inference backend.

    The transformers backend is imported lazily so that mock/CPU runs and the
    test suite never pull in torch/transformers.
    """
    backend = config.model.backend
    if backend == "mock":
        return MockTextGenerator()
    if backend == "transformers":
        from ism.inference.transformers_backend import TransformersTextGenerator

        return TransformersTextGenerator(
            model_name=config.model.reasoner,
            model_revision=config.model.model_revision,
            tokenizer_revision=config.model.tokenizer_revision,
            load_in_4bit=config.model.load_in_4bit,
            device=config.runtime.device,
            temperature=config.model.temperature,
        )
    raise ValueError(f"unknown backend: {backend}")


__all__ = ["build_text_generator"]
