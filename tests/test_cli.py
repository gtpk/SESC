from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE_CONFIG = ROOT / "configs/experiments/smoke.yaml"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ism", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_p0_reg_001_help_succeeds() -> None:
    result = run_cli("--help")

    assert result.returncode == 0
    assert "validate-config" in result.stdout
    assert "dry-run" in result.stdout
    assert "generate-synthetic" in result.stdout


def test_p0_reg_001_validate_config_succeeds() -> None:
    result = run_cli("validate-config", "--config", str(SMOKE_CONFIG))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["dataset"]["path"] == str(ROOT / "data/processed/synthetic-v1")
    assert payload["output"]["artifact_dir"] == str(ROOT / "artifacts")


def test_p0_reg_001_dry_run_succeeds() -> None:
    result = run_cli("dry-run", "--config", str(SMOKE_CONFIG))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["plan"]["compression_calls"] == 3
    assert payload["plan"]["reasoning_calls"] == 18
    assert payload["plan"]["nominal_calls"] == 21
    assert payload["plan"]["worst_case_calls"] == 63


def test_p0_err_001_invalid_arguments_fail() -> None:
    result = run_cli("not-a-command")

    assert result.returncode != 0
    assert "invalid choice" in result.stderr


def test_p1_cli_001_generate_synthetic(tmp_path: Path) -> None:
    output = tmp_path / "synthetic.jsonl"

    result = run_cli(
        "generate-synthetic",
        "--config",
        str(SMOKE_CONFIG),
        "--output",
        str(output),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["documents"] == 3
    assert payload["questions"] == 6
    assert output.exists()
    assert len(output.read_text(encoding="utf-8").splitlines()) == 3
