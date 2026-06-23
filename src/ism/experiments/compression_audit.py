"""Compress-only audit: capture LLM ISMs and measure their structure.

Runs the compressor over the dataset (no QA), records each ISM, and reports the
diagnostic structure metrics (purity, relations structure, self-containment,
corruption strength) so the Δmap≈0 cause can be attributed to the compressor vs
the reasoner vs the data/intervention. See docs/reviews/llm-ism-diagnostic.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from ism.config import AppConfig
from ism.data.generator import SyntheticGenerator
from ism.experiments.compressor import CompressionError, LlmCompressor
from ism.experiments.diagnostics import (
    analyze_isms,
    definition_self_containment,
    majority_baseline,
    relations_structure_score,
    rule_coverage,
)
from ism.inference.contracts import TextGenerator
from ism.representation.models import ISMRepresentation
from ism.representation.parser import serialize_ism
from ism.representation.tokenizer import WhitespaceTokenCounter


@dataclass(frozen=True)
class CompressionAuditReport:
    run_id: str
    documents: int
    compressed: int
    failures: int
    mean_attempts: float
    mean_rule_coverage: float
    mean_self_containment: float
    mean_relations_structure: float
    mean_corruption_overlap: float
    corruption_preserves_content: float
    majority_baseline: dict[str, float]


def run_compression_audit(
    config: AppConfig,
    *,
    output_dir: Path,
    generator: TextGenerator,
) -> CompressionAuditReport:
    documents = SyntheticGenerator(config.experiment.seed).generate(
        config.dataset.max_documents,
        split=config.experiment.split.value,
    )
    tokenizer = WhitespaceTokenCounter()
    compressor = LlmCompressor(
        generator,
        tokenizer=tokenizer,
        seed=config.experiment.seed,
        max_attempts=config.compression.max_regeneration_attempts,
        max_new_tokens=config.compression.max_new_tokens,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    representations: list[ISMRepresentation] = []
    attempts: list[int] = []
    coverages: list[float] = []
    failures = 0
    records: list[dict[str, object]] = []

    for document in documents:
        try:
            outcome = compressor.compress(document, budget=config.compression.budget)
        except CompressionError as error:
            failures += 1
            records.append({"document_id": document.document_id, "failed": str(error)})
            continue
        representation = outcome.representation
        representations.append(representation)
        attempts.append(outcome.attempts)
        coverage = rule_coverage(document, representation)
        coverages.append(coverage)
        records.append(
            {
                "document_id": document.document_id,
                "attempts": outcome.attempts,
                "n_symbols": len(representation.symbols),
                "n_gold_rules": len(document.graph.rules),
                "rule_coverage": coverage,
                "self_containment": definition_self_containment(representation),
                "relations_structure": relations_structure_score(representation),
                "relations": list(representation.relations),
                "serialized": serialize_ism(representation),
            }
        )

    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records]
    (output_dir / "compressions.jsonl").write_text(
        "".join(line + "\n" for line in lines),
        encoding="utf-8",
    )

    structure = analyze_isms(representations, seed=config.experiment.seed)
    report = CompressionAuditReport(
        run_id=config.experiment.name,
        documents=len(documents),
        compressed=len(representations),
        failures=failures,
        mean_attempts=sum(attempts) / len(attempts) if attempts else 0.0,
        mean_rule_coverage=sum(coverages) / len(coverages) if coverages else 0.0,
        mean_self_containment=structure.mean_self_containment,
        mean_relations_structure=structure.mean_relations_structure,
        mean_corruption_overlap=structure.mean_corruption_overlap,
        corruption_preserves_content=structure.corruption_preserves_content,
        majority_baseline=majority_baseline(documents),
    )
    (output_dir / "compression_audit.json").write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


__all__ = ["CompressionAuditReport", "run_compression_audit"]
