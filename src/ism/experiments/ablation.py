"""Experiment 6.1 — Dictionary Ablation (RQ1).

Wires the deterministic condition matrix (per-condition inputs) into the
inference runner so each condition is answered from its own representation,
then reports AR/CR/ES per condition plus the pre-registered contrasts
(delta_map, delta_symbol) with paired bootstrap CIs and McNemar p-values.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from ism.config import AppConfig
from ism.data.generator import GeneratedDocument, SyntheticGenerator
from ism.evaluation.metrics import ConditionMetric
from ism.evaluation.reporting import report_from_artifacts
from ism.evaluation.statistics import mcnemar_exact, paired_bootstrap_difference
from ism.experiments.audit import write_condition_audit
from ism.experiments.compressor import CompressionError, LlmCompressor
from ism.experiments.conditions import build_condition_matrix
from ism.inference.artifacts import AtomicPredictionStore
from ism.inference.contracts import TextGenerator
from ism.inference.pipeline import build_qa_prompt
from ism.inference.runner import InferenceRunner, InferenceSample
from ism.representation.models import ISMRepresentation
from ism.representation.tokenizer import WhitespaceTokenCounter

# Pre-registered contrasts (paper 6.1): (name, left, right).
_CONTRASTS = (
    ("delta_map", "full_symbol_dict", "corrupted_dict"),
    ("delta_symbol", "symbol_only", "random_symbol"),
)


@dataclass(frozen=True)
class Contrast:
    name: str
    left: str
    right: str
    estimate: float
    ci_lower: float
    ci_upper: float
    mcnemar_p: float
    n: int


@dataclass(frozen=True)
class CompressionStats:
    source: str  # "gold" | "llm"
    documents: int
    compressed: int
    failures: int
    mean_attempts: float


@dataclass(frozen=True)
class AblationSummary:
    run_id: str
    documents: int
    questions: int
    predictions: int
    successful: int
    compression: CompressionStats
    conditions: tuple[ConditionMetric, ...]
    contrasts: tuple[Contrast, ...]


def run_ablation_experiment(
    config: AppConfig,
    *,
    output_dir: Path,
    generator: TextGenerator,
    batch_size: int = 1,
    resume: bool = False,
) -> AblationSummary:
    documents = SyntheticGenerator(config.experiment.seed).generate(
        config.dataset.max_documents,
        split=config.experiment.split.value,
    )
    tokenizer = WhitespaceTokenCounter()

    surviving, ism_representation, compression = _compress_documents(
        documents, config=config, generator=generator, tokenizer=tokenizer
    )

    matrix = build_condition_matrix(
        surviving,
        conditions=tuple(config.conditions),
        budget=config.compression.budget,
        seed=config.experiment.seed,
        tokenizer=tokenizer,
        ism_representation=ism_representation,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "condition_audit.json"
    write_condition_audit(audit_path, matrix)

    questions = {
        question.question_id: question for document in surviving for question in document.questions
    }
    samples = tuple(
        InferenceSample(
            sample_id=f"{item.question_id}:{item.condition}",
            question_id=item.question_id,
            condition=item.condition,
            prompt=build_qa_prompt(
                context=item.input_text,
                question=questions[item.question_id].question,
                answer_type=questions[item.question_id].answer_type,
            ),
            expected_output=questions[item.question_id].answer,
        )
        for item in matrix.inputs
    )

    store = AtomicPredictionStore(output_dir / "predictions.jsonl")
    records = InferenceRunner(
        generator,
        store,
        max_new_tokens=config.execution_budget.max_new_tokens,
        seed=config.experiment.seed,
    ).run(
        samples,
        batch_size=batch_size,
        max_attempts=config.execution_budget.max_generation_attempts,
        resume=resume,
    )

    metrics = report_from_artifacts(
        predictions_path=store.path,
        condition_audit_path=audit_path,
        output_dir=output_dir / "report",
        run_id=config.experiment.name,
    )

    correct_by_condition: dict[str, dict[str, bool]] = {}
    for record in records:
        correct_by_condition.setdefault(record.condition, {})[record.question_id] = record.correct

    contrasts: list[Contrast] = []
    for name, left, right in _CONTRASTS:
        contrast = _contrast(name, left, right, correct_by_condition, seed=config.experiment.seed)
        if contrast is not None:
            contrasts.append(contrast)

    summary = AblationSummary(
        run_id=config.experiment.name,
        documents=len(surviving),
        questions=len(questions),
        predictions=len(records),
        successful=sum(1 for record in records if record.error_kind is None),
        compression=compression,
        conditions=metrics,
        contrasts=tuple(contrasts),
    )
    _write_json(output_dir / "ablation_summary.json", asdict(summary))
    return summary


def _compress_documents(
    documents: tuple[GeneratedDocument, ...],
    *,
    config: AppConfig,
    generator: TextGenerator,
    tokenizer: WhitespaceTokenCounter,
) -> tuple[
    tuple[GeneratedDocument, ...],
    Callable[[GeneratedDocument], ISMRepresentation] | None,
    CompressionStats,
]:
    """Compress documents into ISMs.

    For the mock backend the ISM is the deterministic gold-graph oracle (no
    injected representation). For a real model the LLM compressor produces and
    parses the ISM; documents that never yield a valid ISM are dropped and
    reported as failures (paper §5.4 regeneration/failure reporting).
    """
    if config.model.backend != "transformers":
        stats = CompressionStats(
            source="gold",
            documents=len(documents),
            compressed=len(documents),
            failures=0,
            mean_attempts=1.0,
        )
        return documents, None, stats

    compressor = LlmCompressor(
        generator,
        tokenizer=tokenizer,
        seed=config.experiment.seed,
        max_attempts=config.compression.max_regeneration_attempts,
        max_new_tokens=config.compression.max_new_tokens,
    )
    representations: dict[str, ISMRepresentation] = {}
    attempts: list[int] = []
    failures = 0
    for document in documents:
        try:
            outcome = compressor.compress(document, budget=config.compression.budget)
        except CompressionError:
            failures += 1
            continue
        representations[document.document_id] = outcome.representation
        attempts.append(outcome.attempts)

    surviving = tuple(d for d in documents if d.document_id in representations)
    if not surviving:
        raise CompressionError("no document produced a valid ISM compression")
    stats = CompressionStats(
        source="llm",
        documents=len(documents),
        compressed=len(surviving),
        failures=failures,
        mean_attempts=sum(attempts) / len(attempts) if attempts else 0.0,
    )

    def lookup(document: GeneratedDocument) -> ISMRepresentation:
        return representations[document.document_id]

    return surviving, lookup, stats


def _contrast(
    name: str,
    left: str,
    right: str,
    correct_by_condition: dict[str, dict[str, bool]],
    *,
    seed: int,
) -> Contrast | None:
    if left not in correct_by_condition or right not in correct_by_condition:
        return None
    question_ids = sorted(set(correct_by_condition[left]) & set(correct_by_condition[right]))
    if not question_ids:
        return None
    left_bool = tuple(correct_by_condition[left][q] for q in question_ids)
    right_bool = tuple(correct_by_condition[right][q] for q in question_ids)
    interval = paired_bootstrap_difference(
        tuple(float(v) for v in left_bool),
        tuple(float(v) for v in right_bool),
        seed=seed,
    )
    _, _, p_value = mcnemar_exact(left_bool, right_bool)
    return Contrast(
        name=name,
        left=left,
        right=right,
        estimate=interval.estimate,
        ci_lower=interval.lower,
        ci_upper=interval.upper,
        mcnemar_p=p_value,
        n=len(question_ids),
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = ["AblationSummary", "Contrast", "run_ablation_experiment"]
