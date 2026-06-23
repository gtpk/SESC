from __future__ import annotations

import json
from pathlib import Path

from ism.config import load_config
from ism.experiments.ablation import run_ablation_experiment
from ism.inference.mock import MockTextGenerator

ROOT = Path(__file__).resolve().parents[1]
MOCK_CONFIG = ROOT / "configs/experiments/ablation_mock.yaml"


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
    summary = run_ablation_experiment(
        config, output_dir=tmp_path, generator=MockTextGenerator()
    )
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
    summary = run_ablation_experiment(
        config, output_dir=tmp_path, generator=MockTextGenerator()
    )
    names = {contrast.name for contrast in summary.contrasts}
    assert names == {"delta_map", "delta_symbol"}
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
