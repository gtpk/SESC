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

# Contrasts (paper 6.1, amended in Appendix A.1): (name, left, right).
# - delta_map_derange: label-binding sensitivity (derangement preserves the rule
#   set; secondary diagnostic only).
# - delta_map_flip: dictionary semantic-content sensitivity (conclusions flipped;
#   the amended primary dictionary-dependence contrast).
# - delta_symbol: symbolic-structure sensitivity (symbols vs length-matched noise).
_CONTRASTS = (
    ("delta_map_derange", "full_symbol_dict", "corrupted_dict"),
    ("delta_map_flip", "full_symbol_dict", "flipped_dict"),
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
    doc_offset: int = 0,
    doc_count: int | None = None,
) -> AblationSummary:
    documents = SyntheticGenerator(
        config.experiment.seed,
        document_min_tokens=config.dataset.document_min_tokens,
        document_max_tokens=config.dataset.document_max_tokens,
    ).generate(
        config.dataset.max_documents,
        split=config.experiment.split.value,
    )
    # Shard window: generate the full deterministic set, then slice a stable,
    # disjoint, uniquely-identified window so shards can run/resume independently.
    if doc_offset or doc_count is not None:
        end = len(documents) if doc_count is None else doc_offset + doc_count
        documents = documents[doc_offset:end]
        if not documents:
            raise ValueError("document window is empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    tokenizer = WhitespaceTokenCounter()

    surviving, ism_representation, compression = _compress_documents(
        documents,
        config=config,
        generator=generator,
        tokenizer=tokenizer,
        cache_path=output_dir / "compressions_cache.jsonl",
        resume=resume,
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

    summary = AblationSummary(
        run_id=config.experiment.name,
        documents=len(surviving),
        questions=len(questions),
        predictions=len(records),
        successful=sum(1 for record in records if record.error_kind is None),
        compression=compression,
        conditions=metrics,
        contrasts=_build_contrasts(correct_by_condition, seed=config.experiment.seed),
    )
    _write_json(output_dir / "ablation_summary.json", asdict(summary))
    return summary


def _compress_documents(
    documents: tuple[GeneratedDocument, ...],
    *,
    config: AppConfig,
    generator: TextGenerator,
    tokenizer: WhitespaceTokenCounter,
    cache_path: Path | None = None,
    resume: bool = False,
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

    When `cache_path` is set, each document's outcome (representation or failure)
    is appended as JSONL; with `resume=True` cached documents are not recompressed
    so an interrupted shard resumes cheaply.
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
        max_new_tokens=config.compression.generation_max_new_tokens,
    )
    cached_reps: dict[str, ISMRepresentation] = {}
    cached_failures: set[str] = set()
    if resume:
        cached_reps, cached_failures = _load_compression_cache(cache_path)
    representations: dict[str, ISMRepresentation] = dict(cached_reps)
    attempts: list[int] = []
    failures = 0
    for document in documents:
        if document.document_id in representations or document.document_id in cached_failures:
            continue
        try:
            outcome = compressor.compress(document, budget=config.compression.budget)
        except CompressionError:
            failures += 1
            _append_compression_cache(cache_path, document.document_id, None)
            continue
        representations[document.document_id] = outcome.representation
        attempts.append(outcome.attempts)
        _append_compression_cache(cache_path, document.document_id, outcome.representation)

    failures += len(cached_failures)
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


def _build_contrasts(
    correct_by_condition: dict[str, dict[str, bool]], *, seed: int
) -> tuple[Contrast, ...]:
    contrasts: list[Contrast] = []
    for name, left, right in _CONTRASTS:
        contrast = _contrast(name, left, right, correct_by_condition, seed=seed)
        if contrast is not None:
            contrasts.append(contrast)
    return tuple(contrasts)


def _load_compression_cache(
    path: Path | None,
) -> tuple[dict[str, ISMRepresentation], set[str]]:
    representations: dict[str, ISMRepresentation] = {}
    failures: set[str] = set()
    if path is None or not path.exists():
        return representations, failures
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        document_id = record["document_id"]
        payload = record.get("representation")
        if payload is None:
            failures.add(document_id)
        else:
            representations[document_id] = ISMRepresentation.model_validate(payload)
    return representations, failures


def _append_compression_cache(
    path: Path | None, document_id: str, representation: ISMRepresentation | None
) -> None:
    if path is None:
        return
    dumped = None if representation is None else representation.model_dump(mode="json")
    payload = {"document_id": document_id, "representation": dumped}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def merge_ablation(
    shard_dirs: tuple[Path, ...],
    *,
    output_dir: Path,
    run_id: str,
    seed: int,
) -> AblationSummary:
    """Combine independent ablation shards into one paired evaluation.

    Shards hold disjoint, uniquely-identified documents, so their predictions and
    condition audits concatenate cleanly. Metrics and contrasts are recomputed
    over the combined set; compression stats are summed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    prediction_lines: list[str] = []
    audit_records: list[dict[str, object]] = []
    documents = 0
    compressed = 0
    failures = 0
    attempts_weighted = 0.0
    for shard in shard_dirs:
        prediction_lines.extend(
            line
            for line in (shard / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        audit = json.loads((shard / "condition_audit.json").read_text(encoding="utf-8"))
        audit_records.extend(audit["records"])
        summary = json.loads((shard / "ablation_summary.json").read_text(encoding="utf-8"))
        comp = summary["compression"]
        documents += comp["documents"]
        compressed += comp["compressed"]
        failures += comp["failures"]
        attempts_weighted += comp["mean_attempts"] * max(comp["compressed"], 1)

    combined_predictions = output_dir / "predictions.jsonl"
    combined_predictions.write_text("\n".join(prediction_lines) + "\n", encoding="utf-8")
    combined_audit = output_dir / "condition_audit.json"
    _write_json(combined_audit, {"records": audit_records})

    metrics = report_from_artifacts(
        predictions_path=combined_predictions,
        condition_audit_path=combined_audit,
        output_dir=output_dir / "report",
        run_id=run_id,
    )

    correct_by_condition: dict[str, dict[str, bool]] = {}
    questions: set[str] = set()
    for line in prediction_lines:
        record = json.loads(line)
        correct_by_condition.setdefault(record["condition"], {})[record["question_id"]] = record[
            "correct"
        ]
        questions.add(record["question_id"])

    summary = AblationSummary(
        run_id=run_id,
        documents=compressed,
        questions=len(questions),
        predictions=len(prediction_lines),
        successful=sum(1 for line in prediction_lines if json.loads(line)["error_kind"] is None),
        compression=CompressionStats(
            source="llm",
            documents=documents,
            compressed=compressed,
            failures=failures,
            mean_attempts=attempts_weighted / compressed if compressed else 0.0,
        ),
        conditions=metrics,
        contrasts=_build_contrasts(correct_by_condition, seed=seed),
    )
    _write_json(output_dir / "ablation_summary.json", asdict(summary))
    return summary


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = ["AblationSummary", "Contrast", "merge_ablation", "run_ablation_experiment"]
