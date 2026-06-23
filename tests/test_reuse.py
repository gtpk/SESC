from __future__ import annotations

import json
from pathlib import Path

from ism.config import load_config
from ism.experiments.reuse import run_reuse_experiment

ROOT = Path(__file__).resolve().parents[1]
MOCK_CONFIG = ROOT / "configs/experiments/ablation_mock.yaml"

_FB_SUMMARY = {
    "results": [
        {"method": "full_context", "budget": 0, "accuracy": 0.70, "mean_tokens": 1000.0},
        {"method": "ism", "budget": 128, "accuracy": 0.475, "mean_tokens": 96.0},
        {"method": "model_summary", "budget": 128, "accuracy": 0.80, "mean_tokens": 26.0},
        {"method": "ism", "budget": 256, "accuracy": 0.48, "mean_tokens": 97.0},
    ]
}


def _write_fb(tmp_path: Path) -> Path:
    p = tmp_path / "fb.json"
    p.write_text(json.dumps(_FB_SUMMARY), encoding="utf-8")
    return p


def test_reuse_cost_curves_and_crossover(tmp_path: Path) -> None:
    config = load_config(MOCK_CONFIG)
    summary = run_reuse_experiment(
        config,
        output_dir=tmp_path,
        fixed_budget_summary=_write_fb(tmp_path),
        budget=128,
        ns=(1, 2, 4, 8, 16, 32),
    )
    # budget 128 selects ism@128 and model_summary; ism@256 excluded.
    assert set(summary.method_tokens) == {"ism", "model_summary"}
    assert summary.method_accuracy["model_summary"] == 0.80

    by = {(p.method, p.n): p for p in summary.points}
    x, q = summary.full_tokens, summary.question_tokens
    # full_context cost is linear and serving == end-to-end.
    fc8 = by[("full_context", 8)]
    assert fc8.total_tokens_end_to_end == round(8 * (x + q))
    assert fc8.total_tokens_serving_only == fc8.total_tokens_end_to_end
    # cached serving-only is below end-to-end (one-time compression excluded).
    ms8 = by[("model_summary", 8)]
    assert ms8.total_tokens_serving_only < ms8.total_tokens_end_to_end
    # model_summary (smaller z) eventually beats full context.
    assert summary.crossover_n["model_summary"] is not None
    ms32 = by[("model_summary", 32)].total_tokens_end_to_end
    assert ms32 < by[("full_context", 32)].total_tokens_end_to_end


def test_reuse_requires_full_context(tmp_path: Path) -> None:
    import pytest

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"results": [
        {"method": "ism", "budget": 128, "accuracy": 0.4, "mean_tokens": 90.0}
    ]}), encoding="utf-8")
    with pytest.raises(ValueError, match="full_context"):
        run_reuse_experiment(
            load_config(MOCK_CONFIG), output_dir=tmp_path,
            fixed_budget_summary=bad, budget=128, ns=(1, 2),
        )
