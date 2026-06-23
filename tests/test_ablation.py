from __future__ import annotations

import json
from pathlib import Path

from ism.config import load_config
from ism.experiments.ablation import merge_ablation, run_ablation_experiment
from ism.inference.contracts import GenerationRequest, GenerationResult
from ism.inference.mock import MockTextGenerator

ROOT = Path(__file__).resolve().parents[1]
MOCK_CONFIG = ROOT / "configs/experiments/ablation_mock.yaml"
LLM_CONFIG = ROOT / "configs/experiments/ablation_qwen7b.yaml"

_VALID_ISM = (
    "[DICTIONARY]\n"
    "Z1 := IF condition a THEN risk = HIGH\n"
    "Z2 := IF condition b THEN review = true\n\n"
    "[RELATIONS]\n"
    "Z1 Z2\n"
)


class _FakeLlmGenerator:
    """Emits a parseable ISM for compression requests and echoes the expected
    answer for QA requests, so the LLM-compressor path can be tested offline."""

    def __init__(self) -> None:
        self.compress_calls = 0

    def generate(self, requests: tuple[GenerationRequest, ...]) -> tuple[GenerationResult, ...]:
        results: list[GenerationResult] = []
        for request in requests:
            if ":compress:" in request.request_id:
                self.compress_calls += 1
                text: str | None = _VALID_ISM
            else:
                text = request.expected_output
            results.append(
                GenerationResult(
                    request_id=request.request_id,
                    text=text or "",
                    input_tokens=1,
                    output_tokens=1,
                )
            )
        return tuple(results)


def test_ablation_runs_all_conditions_and_differentiates_inputs(tmp_path: Path) -> None:
    config = load_config(MOCK_CONFIG)
    summary = run_ablation_experiment(
        config,
        output_dir=tmp_path,
        generator=MockTextGenerator(),
    )

    conditions = {metric.condition for metric in summary.conditions}
    assert conditions == {
        "full_context",
        "full_symbol_dict",
        "symbol_only",
        "corrupted_dict",
        "random_symbol",
    }
    # 4 docs x 2 questions x 5 conditions
    assert summary.predictions == 40
    assert summary.successful == 40


def test_ablation_conditions_differ_in_tokens(tmp_path: Path) -> None:
    config = load_config(MOCK_CONFIG)
    summary = run_ablation_experiment(config, output_dir=tmp_path, generator=MockTextGenerator())
    by_condition = {metric.condition: metric for metric in summary.conditions}

    # full_context is the uncompressed baseline (CR == 1); the ISM/symbol
    # representations are strictly shorter, proving each condition is answered
    # from its own input rather than the full document.
    assert by_condition["full_context"].compression_ratio == 1.0
    assert by_condition["full_symbol_dict"].compression_ratio is not None
    assert by_condition["full_symbol_dict"].compression_ratio < 1.0
    assert by_condition["symbol_only"].compression_ratio is not None
    assert (
        by_condition["symbol_only"].compression_ratio
        < by_condition["full_symbol_dict"].compression_ratio
    )


def test_ablation_reports_preregistered_contrasts(tmp_path: Path) -> None:
    config = load_config(MOCK_CONFIG)
    summary = run_ablation_experiment(config, output_dir=tmp_path, generator=MockTextGenerator())
    names = {contrast.name for contrast in summary.contrasts}
    # The mock config has no flipped_dict, so delta_map_flip is absent here.
    assert names == {"delta_map_derange", "delta_symbol"}
    # Mock answers everything correctly, so both contrasts are exactly zero.
    for contrast in summary.contrasts:
        assert contrast.estimate == 0.0
        assert contrast.n == 8  # 4 docs x 2 questions


def test_ablation_writes_artifacts(tmp_path: Path) -> None:
    config = load_config(MOCK_CONFIG)
    run_ablation_experiment(config, output_dir=tmp_path, generator=MockTextGenerator())

    for name in ["predictions.jsonl", "condition_audit.json", "ablation_summary.json"]:
        assert (tmp_path / name).is_file()
    assert (tmp_path / "report" / "metrics.json").is_file()
    summary = json.loads((tmp_path / "ablation_summary.json").read_text())
    assert summary["run_id"] == "ablation-mock"
    assert len(summary["conditions"]) == 5


def test_mock_backend_uses_gold_compression(tmp_path: Path) -> None:
    config = load_config(MOCK_CONFIG)
    summary = run_ablation_experiment(config, output_dir=tmp_path, generator=MockTextGenerator())
    assert summary.compression.source == "gold"
    assert summary.compression.failures == 0


def test_llm_backend_uses_llm_compressor(tmp_path: Path) -> None:
    config = load_config(LLM_CONFIG)
    summary = run_ablation_experiment(config, output_dir=tmp_path, generator=_FakeLlmGenerator())
    assert summary.compression.source == "llm"
    assert summary.compression.compressed == config.dataset.max_documents
    assert summary.compression.failures == 0
    assert summary.compression.mean_attempts == 1.0
    # All 7 conditions are produced from the LLM-generated ISM.
    assert {metric.condition for metric in summary.conditions} == {
        "full_context",
        "full_symbol_dict",
        "symbol_only",
        "corrupted_dict",
        "flipped_dict",
        "blank_dict",
        "random_symbol",
    }
    # Label-binding, semantic-content, and structure contrasts are reported.
    assert {c.name for c in summary.contrasts} == {
        "delta_map_derange",
        "delta_map_flip",
        "delta_symbol",
    }


def test_shard_window_selects_disjoint_documents(tmp_path: Path) -> None:
    config = load_config(MOCK_CONFIG)  # 4 docs, 5 conditions
    summary = run_ablation_experiment(
        config,
        output_dir=tmp_path,
        generator=MockTextGenerator(),
        doc_offset=2,
        doc_count=2,
    )
    assert summary.documents == 2
    assert summary.predictions == 2 * 2 * 5  # 2 docs x 2 questions x 5 conditions


def test_compression_cache_resume_skips_recompression(tmp_path: Path) -> None:
    config = load_config(LLM_CONFIG)
    generator = _FakeLlmGenerator()

    first = run_ablation_experiment(
        config, output_dir=tmp_path, generator=generator, doc_count=2
    )
    assert first.compression.compressed == 2
    assert generator.compress_calls == 2
    assert (tmp_path / "compressions_cache.jsonl").is_file()

    # Resuming reuses the cached ISMs: no further compression generations.
    generator.compress_calls = 0
    second = run_ablation_experiment(
        config, output_dir=tmp_path, generator=generator, doc_count=2, resume=True
    )
    assert generator.compress_calls == 0
    assert second.compression.compressed == 2


def test_merge_ablation_combines_disjoint_shards(tmp_path: Path) -> None:
    config = load_config(MOCK_CONFIG)  # 4 docs
    shard_a = tmp_path / "a"
    shard_b = tmp_path / "b"
    run_ablation_experiment(
        config, output_dir=shard_a, generator=MockTextGenerator(), doc_offset=0, doc_count=2
    )
    run_ablation_experiment(
        config, output_dir=shard_b, generator=MockTextGenerator(), doc_offset=2, doc_count=2
    )

    merged = merge_ablation(
        (shard_a, shard_b),
        output_dir=tmp_path / "merged",
        run_id="merged",
        seed=42,
    )
    assert merged.documents == 4
    assert merged.predictions == 4 * 2 * 5
    assert {c.name for c in merged.contrasts} == {"delta_map_derange", "delta_symbol"}
    assert (tmp_path / "merged" / "ablation_summary.json").is_file()
