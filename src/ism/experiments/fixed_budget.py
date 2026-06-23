"""Experiment 6.3 — Fixed-Budget Comparison (RQ3).

For each token budget B and method, produce a within-budget context, answer the
questions, and report the accuracy / compression-ratio / efficiency frontier.
Budget fairness is enforced by the producers (selection or regeneration, never
truncation). full_context is the CR=1 reference; oracle_gold_summary is an
upper-bound reference, not a usable method. LLMLingua-2 is omitted (follow-up).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from ism.config import AppConfig
from ism.data.generator import GeneratedDocument, GeneratedQuestion, SyntheticGenerator
from ism.experiments.compressor import CompressionError, LlmCompressor
from ism.experiments.methods import (
    compute_idf,
    full_context_text,
    ism_text,
    keyword_extract_text,
    model_summary_text,
    oracle_gold_summary_text,
)
from ism.inference.artifacts import AtomicPredictionStore
from ism.inference.contracts import TextGenerator
from ism.inference.pipeline import build_qa_prompt
from ism.inference.runner import InferenceRunner, InferenceSample
from ism.inference.runner_models import PredictionRecord
from ism.representation.tokenizer import WhitespaceTokenCounter

_FULL_CONTEXT = "full_context"


@dataclass(frozen=True)
class MethodBudgetMetric:
    method: str
    budget: int
    accuracy: float
    accuracy_retention: float | None
    compression_ratio: float | None
    efficiency_score: float | None
    questions: int
    produced_docs: int
    failed_docs: int
    mean_tokens: float


@dataclass(frozen=True)
class FixedBudgetSummary:
    run_id: str
    documents: int
    budgets: tuple[int, ...]
    methods: tuple[str, ...]
    predictions: int
    successful: int
    results: tuple[MethodBudgetMetric, ...]


def run_fixed_budget_experiment(
    config: AppConfig,
    *,
    output_dir: Path,
    generator: TextGenerator,
    budgets: tuple[int, ...],
    methods: tuple[str, ...],
    batch_size: int = 1,
    resume: bool = False,
    doc_offset: int = 0,
    doc_count: int | None = None,
) -> FixedBudgetSummary:
    if not budgets or any(b < 1 for b in budgets):
        raise ValueError("budgets must be positive")
    if _FULL_CONTEXT not in methods:
        raise ValueError("methods must include full_context (the CR=1 reference)")

    documents = SyntheticGenerator(
        config.experiment.seed,
        document_min_tokens=config.dataset.document_min_tokens,
        document_max_tokens=config.dataset.document_max_tokens,
    ).generate(
        config.dataset.max_documents, split=config.experiment.split.value
    )
    if doc_offset or doc_count is not None:
        end = len(documents) if doc_count is None else doc_offset + doc_count
        documents = documents[doc_offset:end]
        if not documents:
            raise ValueError("document window is empty")
    output_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = WhitespaceTokenCounter()
    idf = compute_idf(documents)
    compressor = LlmCompressor(
        generator,
        tokenizer=tokenizer,
        seed=config.experiment.seed,
        max_attempts=config.compression.max_regeneration_attempts,
        max_new_tokens=config.compression.generation_max_new_tokens,
    )

    # cell_key -> {document_id: text}; cell_key = (method, budget) with full_context at budget 0.
    cell_texts: dict[tuple[str, int], dict[str, str]] = {}
    cell_failures: dict[tuple[str, int], int] = {}

    def _record(method: str, budget: int, document_id: str, text: str | None) -> None:
        key = (method, budget)
        cell_texts.setdefault(key, {})
        cell_failures.setdefault(key, 0)
        if text is None:
            cell_failures[key] += 1
        else:
            cell_texts[key][document_id] = text

    for document in documents:
        for method in methods:
            if method == _FULL_CONTEXT:
                _record(method, 0, document.document_id, full_context_text(document))
                continue
            for budget in budgets:
                try:
                    text = _produce(
                        method,
                        document,
                        budget=budget,
                        idf=idf,
                        compressor=compressor,
                        generator=generator,
                        config=config,
                        tokenizer=tokenizer,
                    )
                except CompressionError:
                    _record(method, budget, document.document_id, None)
                    continue
                _record(method, budget, document.document_id, text)

    _write_contexts(output_dir / "contexts.jsonl", cell_texts, tokenizer)

    samples: list[InferenceSample] = []
    for (method, budget), texts in cell_texts.items():
        for document_id, text in texts.items():
            for question in _questions_for(document_id, documents):
                samples.append(
                    InferenceSample(
                        sample_id=f"{question.question_id}:{method}:{budget}",
                        question_id=question.question_id,
                        condition=f"{method}@{budget}",
                        prompt=build_qa_prompt(
                            context=text,
                            question=question.question,
                            answer_type=question.answer_type,
                        ),
                        expected_output=question.answer,
                    )
                )

    store = AtomicPredictionStore(output_dir / "predictions.jsonl")
    records = InferenceRunner(
        generator,
        store,
        max_new_tokens=config.execution_budget.max_new_tokens,
        seed=config.experiment.seed,
    ).run(
        tuple(samples),
        batch_size=batch_size,
        max_attempts=config.execution_budget.max_generation_attempts,
        resume=resume,
    )

    results = _build_results(
        records=records,
        cell_texts=cell_texts,
        cell_failures=cell_failures,
        tokenizer=tokenizer,
        budgets=budgets,
        methods=methods,
    )
    summary = FixedBudgetSummary(
        run_id=config.experiment.name,
        documents=len(documents),
        budgets=tuple(budgets),
        methods=tuple(methods),
        predictions=len(records),
        successful=sum(1 for r in records if r.error_kind is None),
        results=results,
    )
    (output_dir / "fixed_budget_summary.json").write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _produce(
    method: str,
    document: GeneratedDocument,
    *,
    budget: int,
    idf: dict[str, float],
    compressor: LlmCompressor,
    generator: TextGenerator,
    config: AppConfig,
    tokenizer: WhitespaceTokenCounter,
) -> str:
    if method == "ism":
        return ism_text(document, budget=budget, compressor=compressor)
    if method == "keyword_extract":
        return keyword_extract_text(document, budget=budget, idf=idf)
    if method == "oracle_gold_summary":
        return oracle_gold_summary_text(document, budget=budget)
    if method == "model_summary":
        return model_summary_text(
            document,
            budget=budget,
            generator=generator,
            seed=config.experiment.seed,
            max_attempts=config.compression.max_regeneration_attempts,
            max_new_tokens=config.compression.generation_max_new_tokens,
            tokenizer=tokenizer,
        )
    raise ValueError(f"unsupported fixed-budget method: {method}")


def _questions_for(
    document_id: str, documents: tuple[GeneratedDocument, ...]
) -> tuple[GeneratedQuestion, ...]:
    for document in documents:
        if document.document_id == document_id:
            return document.questions
    return ()


def _build_results(
    *,
    records: tuple[PredictionRecord, ...],
    cell_texts: dict[tuple[str, int], dict[str, str]],
    cell_failures: dict[tuple[str, int], int],
    tokenizer: WhitespaceTokenCounter,
    budgets: tuple[int, ...],
    methods: tuple[str, ...],
) -> tuple[MethodBudgetMetric, ...]:
    correct: dict[str, list[bool]] = {}
    for record in records:
        correct.setdefault(record.condition, []).append(record.correct)

    def _accuracy(condition: str) -> float | None:
        values = correct.get(condition)
        return sum(values) / len(values) if values else None

    full_accuracy = _accuracy(f"{_FULL_CONTEXT}@0")
    full_tokens = _mean_tokens(cell_texts.get((_FULL_CONTEXT, 0), {}), tokenizer)

    results: list[MethodBudgetMetric] = []
    cells = [(_FULL_CONTEXT, 0)] + [
        (m, b) for m in methods if m != _FULL_CONTEXT for b in budgets
    ]
    for method, budget in cells:
        condition = f"{method}@{budget}"
        accuracy = _accuracy(condition)
        if accuracy is None:
            continue
        mean_tokens = _mean_tokens(cell_texts.get((method, budget), {}), tokenizer)
        ar = accuracy / full_accuracy if full_accuracy else None
        cr = mean_tokens / full_tokens if full_tokens else None
        es = ar / cr if ar is not None and cr not in (None, 0) else None
        results.append(
            MethodBudgetMetric(
                method=method,
                budget=budget,
                accuracy=accuracy,
                accuracy_retention=ar,
                compression_ratio=cr,
                efficiency_score=es,
                questions=len(correct[condition]),
                produced_docs=len(cell_texts.get((method, budget), {})),
                failed_docs=cell_failures.get((method, budget), 0),
                mean_tokens=mean_tokens,
            )
        )
    return tuple(results)


def _write_contexts(
    path: Path,
    cell_texts: dict[tuple[str, int], dict[str, str]],
    tokenizer: WhitespaceTokenCounter,
) -> None:
    """Persist each produced context with its token count for budget auditing."""
    lines: list[str] = []
    for (method, budget), texts in sorted(cell_texts.items()):
        for document_id, text in sorted(texts.items()):
            lines.append(
                json.dumps(
                    {
                        "method": method,
                        "budget": budget,
                        "document_id": document_id,
                        "tokens": tokenizer.count(text),
                        "text": text,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")


def _mean_tokens(texts: dict[str, str], tokenizer: WhitespaceTokenCounter) -> float:
    if not texts:
        return 0.0
    return sum(tokenizer.count(text) for text in texts.values()) / len(texts)


__all__ = ["FixedBudgetSummary", "MethodBudgetMetric", "run_fixed_budget_experiment"]
