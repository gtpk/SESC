from __future__ import annotations

import sys
from pathlib import Path

from ism.config import load_config
from ism.inference.artifacts import AtomicPredictionStore
from ism.inference.contracts import ErrorKind, GenerationRequest
from ism.inference.factory import build_text_generator
from ism.inference.mock import MockTextGenerator
from ism.inference.runner import InferenceRunner, InferenceSample
from ism.inference.transformers_backend import TransformersTextGenerator

ROOT = Path(__file__).resolve().parents[1]
SMOKE_CONFIG = ROOT / "configs/experiments/smoke.yaml"
S1_CONFIG = ROOT / "configs/experiments/s1_qwen7b.yaml"


def _make(**overrides: object) -> TransformersTextGenerator:
    params: dict[str, object] = {
        "model_name": "stub-model",
        "model_revision": "main",
        "tokenizer_revision": "main",
        "load_in_4bit": False,
        "device": "cpu",
        "temperature": 0.0,
    }
    params.update(overrides)
    return TransformersTextGenerator(**params)  # type: ignore[arg-type]


def _req(request_id: str, prompt: str = "hi there") -> GenerationRequest:
    return GenerationRequest(
        request_id=request_id,
        prompt=prompt,
        max_new_tokens=16,
        seed=42,
    )


class _EchoGenerator(TransformersTextGenerator):
    def _generate_text(
        self, prompt: str, *, max_new_tokens: int, seed: int
    ) -> tuple[str, int, int]:
        return f"echo:{prompt}", len(prompt.split()), 1


class _RaisingGenerator(TransformersTextGenerator):
    def __init__(self, error: Exception, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._error = error

    def _generate_text(
        self, prompt: str, *, max_new_tokens: int, seed: int
    ) -> tuple[str, int, int]:
        raise self._error


def test_p3_arc_003_constructing_backend_does_not_load_torch() -> None:
    # The heavy deps are imported lazily; building the adapter must not require
    # or import torch, so mock/CPU runs and this suite never pull it in.
    assert "torch" not in sys.modules
    generator = _make()
    assert not generator.loaded
    assert "torch" not in sys.modules


def test_p3_arc_004_factory_selects_mock_for_mock_backend() -> None:
    generator = build_text_generator(load_config(SMOKE_CONFIG))
    assert isinstance(generator, MockTextGenerator)


def test_p3_arc_004_factory_selects_transformers_for_transformers_backend() -> None:
    config = load_config(S1_CONFIG)
    generator = build_text_generator(config)

    assert isinstance(generator, TransformersTextGenerator)
    assert generator.model_name == config.model.reasoner
    assert generator.load_in_4bit is True
    assert generator.device == "cuda"
    assert not generator.loaded  # still not loaded


def test_p3_con_002_transformers_success_contract() -> None:
    results = _EchoGenerator(
        model_name="m",
        model_revision="main",
        tokenizer_revision="main",
        load_in_4bit=False,
        device="cpu",
    ).generate((_req("a", "one two"), _req("b", "x")))

    assert [r.request_id for r in results] == ["a", "b"]
    assert results[0].succeeded
    assert results[0].text == "echo:one two"
    assert results[0].input_tokens == 2
    assert results[0].output_tokens == 1
    assert all(r.latency_ms >= 0 for r in results)


def test_p3_err_003_oom_exception_becomes_oom_failure_result() -> None:
    (result,) = _RaisingGenerator(
        RuntimeError("CUDA out of memory"),
        model_name="m",
        model_revision="main",
        tokenizer_revision="main",
        load_in_4bit=True,
        device="cuda",
    ).generate((_req("a"),))

    assert not result.succeeded
    assert result.error_kind is ErrorKind.OUT_OF_MEMORY
    assert result.text is None
    assert result.error_message


def test_p3_err_003_value_error_becomes_validation_failure_result() -> None:
    (result,) = _RaisingGenerator(
        ValueError("bad prompt"),
        model_name="m",
        model_revision="main",
        tokenizer_revision="main",
        load_in_4bit=False,
        device="cpu",
    ).generate((_req("a"),))

    assert result.error_kind is ErrorKind.VALIDATION
    assert result.error_message == "bad prompt"


def test_p3_arc_005_transformers_adapter_is_substitutable_in_runner(tmp_path: Path) -> None:
    generator = _EchoGenerator(
        model_name="m",
        model_revision="main",
        tokenizer_revision="main",
        load_in_4bit=False,
        device="cpu",
    )
    sample = InferenceSample(
        sample_id="s1",
        question_id="q1",
        condition="full_context",
        prompt="hello world",
        expected_output="echo:hello world",
    )
    records = InferenceRunner(
        generator,
        AtomicPredictionStore(tmp_path / "predictions.jsonl"),
        max_new_tokens=16,
        seed=42,
    ).run((sample,), batch_size=1, max_attempts=1)

    assert len(records) == 1
    assert records[0].prediction_raw == "echo:hello world"
    assert records[0].correct is True
    assert records[0].error_kind is None


def test_s1_qwen7b_config_is_valid_server_stage() -> None:
    config = load_config(S1_CONFIG)

    assert config.execution_budget.stage.value == "S1"
    assert config.model.backend == "transformers"
    assert config.model.load_in_4bit is True
    assert config.runtime.device == "cuda"
    assert config.execution_budget.max_gpu_hours > 0
