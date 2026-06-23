from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ism.config import AppConfig
from ism.data.generator import SyntheticGenerator
from ism.inference.artifacts import AtomicPredictionStore
from ism.inference.contracts import TextGenerator
from ism.inference.runner import InferenceRunner, InferenceSample


@dataclass(frozen=True)
class PipelineSummary:
    run_id: str
    documents: int
    questions: int
    predictions: int
    successful: int
    correct: int
    accuracy: float
    artifact_dir: str


def build_qa_prompt(*, context: str, question: str, answer_type: str) -> str:
    """Build a QA prompt that constrains the model to a short, scorable answer.

    The synthetic answers are single-token classifications ("HIGH"/"LOW") or
    booleans ("True"/"False"); without a format instruction an instruct model
    emits long chain-of-thought that never exact-matches.
    """
    if answer_type == "boolean":
        instruction = "Respond with exactly one word: True or False. No explanation."
    else:
        instruction = "Respond with only the final answer in a single word. No explanation."
    return f"{instruction}\n\nContext:\n{context}\n\nQuestion: {question}\nAnswer:"


def run_pipeline(
    config: AppConfig,
    *,
    output_dir: Path,
    generator: TextGenerator,
    batch_size: int = 1,
    resume: bool = False,
) -> PipelineSummary:
    documents = SyntheticGenerator(
        config.experiment.seed,
        document_min_tokens=config.dataset.document_min_tokens,
        document_max_tokens=config.dataset.document_max_tokens,
    ).generate(
        config.dataset.max_documents,
        split=config.experiment.split.value,
    )
    samples = tuple(
        InferenceSample(
            sample_id=f"{question.question_id}:{condition}",
            question_id=question.question_id,
            condition=condition,
            prompt=build_qa_prompt(
                context=document.document_text,
                question=question.question,
                answer_type=question.answer_type,
            ),
            expected_output=question.answer,
        )
        for document in documents
        for question in document.questions[: config.dataset.questions_per_document]
        for condition in config.conditions
    )
    output_dir.mkdir(parents=True, exist_ok=True)
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
    successful = [record for record in records if record.error_kind is None]
    correct = sum(record.correct for record in successful)
    summary = PipelineSummary(
        run_id=config.experiment.name,
        documents=len(documents),
        questions=sum(len(document.questions) for document in documents),
        predictions=len(records),
        successful=len(successful),
        correct=correct,
        accuracy=correct / len(successful) if successful else 0,
        artifact_dir=str(output_dir.resolve()),
    )
    _write_json_atomic(output_dir / "metrics.json", asdict(summary))
    _write_json_atomic(
        output_dir / "manifest.json",
        {
            "run_id": config.experiment.name,
            "config_hash": config.config_hash(),
            "backend": config.model.backend,
            "model_revision": config.model.model_revision,
            "tokenizer_revision": config.model.tokenizer_revision,
            "seed": config.experiment.seed,
            "split": config.experiment.split.value,
            "conditions": config.conditions,
            "status": "completed",
        },
    )
    return summary


# Backward-compatible alias: the pipeline is backend-agnostic (it accepts any
# TextGenerator), so it is no longer mock-specific.
run_mock_pipeline = run_pipeline


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
