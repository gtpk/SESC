"""Experiment 6.4 — Reuse cost/accuracy tradeoff (RQ4).

When one compressed representation is reused across n questions per document,
the input-token cost is analytic (paper §6.4):

    full_context:      T_full(n)  = n * (|x| + |q|)
    cached (ISM/sum):  T_cache(n) = |x| + |z| + n * (|z| + |q|)   (end-to-end)
                       T_serve(n) = n * (|z| + |q|)               (serving-only)

|x| = full document tokens, |z| = compressed tokens, |q| = question tokens. The
leading |x| in the cached end-to-end cost is the one-time compression read.
Per-question accuracy does not depend on n (the same cache answers every
question), so accuracy is a method-level constant taken from the fixed-budget
run; the experiment characterizes the cost-accuracy tradeoff, not an ISM win.
No GPU: token counts and accuracy come from the 6.3 artifact.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from ism.config import AppConfig
from ism.data.generator import SyntheticGenerator
from ism.representation.tokenizer import WhitespaceTokenCounter

_FULL_CONTEXT = "full_context"


@dataclass(frozen=True)
class ReusePoint:
    method: str
    n: int
    accuracy: float
    total_tokens_end_to_end: int
    total_tokens_serving_only: int
    tokens_per_question_end_to_end: float


@dataclass(frozen=True)
class ReuseSummary:
    run_id: str
    budget: int
    full_tokens: float  # |x|
    question_tokens: float  # |q|
    method_tokens: dict[str, float]  # |z| per cached method
    method_accuracy: dict[str, float]
    ns: tuple[int, ...]
    points: tuple[ReusePoint, ...]
    crossover_n: dict[str, int | None]  # first n where cached end-to-end < full_context


def run_reuse_experiment(
    config: AppConfig,
    *,
    output_dir: Path,
    fixed_budget_summary: Path,
    budget: int,
    ns: tuple[int, ...] = (1, 2, 4, 8, 16, 32, 64),
) -> ReuseSummary:
    documents = SyntheticGenerator(
        config.experiment.seed,
        document_min_tokens=config.dataset.document_min_tokens,
        document_max_tokens=config.dataset.document_max_tokens,
    ).generate(config.dataset.max_documents, split=config.experiment.split.value)
    tokenizer = WhitespaceTokenCounter()
    x = sum(tokenizer.count(d.document_text) for d in documents) / len(documents)
    question_counts = [tokenizer.count(q.question) for d in documents for q in d.questions]
    q = sum(question_counts) / len(question_counts)

    summary = json.loads(fixed_budget_summary.read_text(encoding="utf-8"))
    cached_z: dict[str, float] = {}
    accuracy: dict[str, float] = {}
    for row in summary["results"]:
        if row["method"] == _FULL_CONTEXT:
            accuracy[_FULL_CONTEXT] = row["accuracy"]
        elif row["budget"] == budget:
            cached_z[row["method"]] = row["mean_tokens"]
            accuracy[row["method"]] = row["accuracy"]
    if _FULL_CONTEXT not in accuracy:
        raise ValueError("fixed-budget summary missing full_context")
    if not cached_z:
        raise ValueError(f"no cached methods at budget {budget}")

    output_dir.mkdir(parents=True, exist_ok=True)
    points: list[ReusePoint] = []
    crossover: dict[str, int | None] = {}

    for n in ns:
        full_cost = round(n * (x + q))
        points.append(
            ReusePoint(
                method=_FULL_CONTEXT,
                n=n,
                accuracy=accuracy[_FULL_CONTEXT],
                total_tokens_end_to_end=full_cost,
                total_tokens_serving_only=full_cost,
                tokens_per_question_end_to_end=full_cost / n,
            )
        )
    for method, z in sorted(cached_z.items()):
        crossover[method] = None
        for n in ns:
            end_to_end = round(x + z + n * (z + q))
            serving = round(n * (z + q))
            full_cost = n * (x + q)
            if crossover[method] is None and end_to_end < full_cost:
                crossover[method] = n
            points.append(
                ReusePoint(
                    method=method,
                    n=n,
                    accuracy=accuracy[method],
                    total_tokens_end_to_end=end_to_end,
                    total_tokens_serving_only=serving,
                    tokens_per_question_end_to_end=end_to_end / n,
                )
            )

    result = ReuseSummary(
        run_id=config.experiment.name,
        budget=budget,
        full_tokens=x,
        question_tokens=q,
        method_tokens=cached_z,
        method_accuracy=accuracy,
        ns=tuple(ns),
        points=tuple(points),
        crossover_n=crossover,
    )
    (output_dir / "reuse_summary.json").write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


__all__ = ["ReusePoint", "ReuseSummary", "run_reuse_experiment"]
