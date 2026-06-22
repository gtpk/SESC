from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from pydantic import TypeAdapter

from ism.data.generator import GeneratedDocument

_DOCUMENT_ADAPTER = TypeAdapter(tuple[GeneratedDocument, ...])


def write_documents(path: Path, documents: Iterable[GeneratedDocument]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payloads = [_document_to_dict(document) for document in documents]
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as stream:
            for payload in payloads:
                stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def read_documents(path: Path) -> tuple[GeneratedDocument, ...]:
    payloads: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {error.msg}") from error
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: document record must be an object")
            payloads.append(cast(dict[str, Any], value))
    return _DOCUMENT_ADAPTER.validate_python(payloads)


def _document_to_dict(document: GeneratedDocument) -> dict[str, Any]:
    return {
        "document_id": document.document_id,
        "split": document.split,
        "document_text": document.document_text,
        "graph": document.graph.model_dump(mode="json"),
        "questions": [
            {
                "question_id": question.question_id,
                "document_id": question.document_id,
                "question": question.question,
                "answer": question.answer,
                "answer_type": question.answer_type,
                "required_rule_ids": list(question.required_rule_ids),
                "ood_type": question.ood_type,
            }
            for question in document.questions
        ],
        "generator_version": document.generator_version,
        "seed": document.seed,
    }
