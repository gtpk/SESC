from __future__ import annotations

import json
from pathlib import Path

from ism.config import load_config
from ism.experiments.compression_audit import run_compression_audit
from ism.inference.contracts import GenerationRequest, GenerationResult

ROOT = Path(__file__).resolve().parents[1]
LLM_CONFIG = ROOT / "configs/experiments/ablation_qwen7b.yaml"

_ISM = "[DICTIONARY]\nZ1 := condition a\nZ2 := condition b\n\n[RELATIONS]\nZ1 Z2\n"


class _FakeCompressor:
    def generate(
        self, requests: tuple[GenerationRequest, ...]
    ) -> tuple[GenerationResult, ...]:
        return tuple(
            GenerationResult(request_id=r.request_id, text=_ISM, input_tokens=1, output_tokens=1)
            for r in requests
        )


def test_compression_audit_reports_structure(tmp_path: Path) -> None:
    config = load_config(LLM_CONFIG)
    report = run_compression_audit(config, output_dir=tmp_path, generator=_FakeCompressor())

    assert report.compressed == config.dataset.max_documents
    assert report.failures == 0
    # The fake ISM has a bare label relation -> no structure.
    assert report.mean_relations_structure == 0.0
    assert (tmp_path / "compressions.jsonl").is_file()
    assert (tmp_path / "compression_audit.json").is_file()
    records = [
        json.loads(line)
        for line in (tmp_path / "compressions.jsonl").read_text().splitlines()
    ]
    assert len(records) == config.dataset.max_documents
    assert all("serialized" in r for r in records)
