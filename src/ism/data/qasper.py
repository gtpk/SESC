from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, cast

from ism.data.contracts import (
    AnswerRecord,
    AnswerType,
    DocumentRecord,
    EvidenceLink,
    QuestionRecord,
)


@dataclass(frozen=True)
class QuarantineItem:
    document_id: str
    question_id: str | None
    reason: str


@dataclass(frozen=True)
class QasperLoadResult:
    documents: tuple[DocumentRecord, ...]
    quarantine: tuple[QuarantineItem, ...]


class QasperAdapter:
    def load(
        self,
        raw_papers: dict[str, Any],
        *,
        split: str,
        tuning_mode: bool = False,
    ) -> QasperLoadResult:
        if split not in {"train", "dev", "test"}:
            raise ValueError(f"unknown split: {split}")
        if split == "test" and tuning_mode:
            raise ValueError("test split cannot be loaded in tuning mode")

        documents: list[DocumentRecord] = []
        quarantine: list[QuarantineItem] = []
        for paper_id in sorted(raw_papers):
            raw = raw_papers[paper_id]
            try:
                documents.append(
                    self._map_paper(
                        paper_id,
                        _mapping(raw, f"paper {paper_id}"),
                        split=split,
                        quarantine=quarantine,
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                quarantine.append(
                    QuarantineItem(
                        document_id=paper_id,
                        question_id=None,
                        reason=str(error),
                    )
                )
        return QasperLoadResult(documents=tuple(documents), quarantine=tuple(quarantine))

    def _map_paper(
        self,
        paper_id: str,
        raw: dict[str, Any],
        *,
        split: str,
        quarantine: list[QuarantineItem],
    ) -> DocumentRecord:
        title = _string(raw, "title")
        abstract_parts = _string_list(raw.get("abstract"), "abstract")
        sections = _mapping(raw.get("full_text"), "full_text")
        section_names = _string_list(sections.get("section_name"), "full_text.section_name")
        paragraphs_by_section = _nested_string_list(
            sections.get("paragraphs"),
            "full_text.paragraphs",
        )
        if len(section_names) != len(paragraphs_by_section):
            raise ValueError("full_text section_name and paragraphs lengths differ")
        document_text, paragraph_locations = _render_document(
            title,
            abstract_parts,
            section_names,
            paragraphs_by_section,
        )

        questions: list[QuestionRecord] = []
        raw_questions = _list(raw.get("qas"), "qas")
        for raw_question_value in raw_questions:
            question_id: str | None = None
            try:
                raw_question = _mapping(raw_question_value, "question")
                question_id = _string(raw_question, "question_id")
                questions.append(
                    _map_question(
                        paper_id,
                        raw_question,
                        document_text=document_text,
                        paragraph_locations=paragraph_locations,
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                quarantine.append(
                    QuarantineItem(
                        document_id=paper_id,
                        question_id=question_id,
                        reason=str(error),
                    )
                )
        return DocumentRecord(
            document_id=paper_id,
            split=split,
            title=title,
            abstract="\n".join(abstract_parts),
            document_text=document_text,
            questions=tuple(questions),
        )


def stable_adapter_digest(result: QasperLoadResult) -> str:
    payload = "\n---\n".join(
        "\n".join(
            (
                document.document_id,
                document.split,
                document.title,
                document.abstract,
                document.document_text,
                *(
                    f"{question.question_id}|{question.question}|"
                    + ";".join(
                        f"{answer.answer_type.value}:{answer.text}" for answer in question.answers
                    )
                    for question in document.questions
                ),
            )
        )
        for document in result.documents
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _map_question(
    paper_id: str,
    raw: dict[str, Any],
    *,
    document_text: str,
    paragraph_locations: dict[str, tuple[int, int, str, int]],
) -> QuestionRecord:
    question_id = _string(raw, "question_id")
    question = _string(raw, "question")
    raw_answers = _list(raw.get("answers"), "answers")
    answers = tuple(
        _map_answer(
            _mapping(_mapping(item, "answer wrapper").get("answer"), "answer"),
            document_text=document_text,
            paragraph_locations=paragraph_locations,
        )
        for item in raw_answers
    )
    if not answers:
        raise ValueError("question must contain at least one answer")
    return QuestionRecord(
        question_id=question_id,
        document_id=paper_id,
        question=question,
        answers=answers,
    )


def _map_answer(
    raw: dict[str, Any],
    *,
    document_text: str,
    paragraph_locations: dict[str, tuple[int, int, str, int]],
) -> AnswerRecord:
    unanswerable = raw.get("unanswerable")
    yes_no = raw.get("yes_no")
    extractive = _string_list(raw.get("extractive_spans", []), "extractive_spans")
    free_form = raw.get("free_form_answer", "")

    if unanswerable is True:
        answer_type = AnswerType.UNANSWERABLE
        text = "Unanswerable"
    elif isinstance(yes_no, bool):
        answer_type = AnswerType.YES_NO
        text = "Yes" if yes_no else "No"
    elif extractive:
        answer_type = AnswerType.EXTRACTIVE
        text = ", ".join(extractive)
    elif isinstance(free_form, str) and free_form.strip():
        answer_type = AnswerType.ABSTRACTIVE
        text = free_form.strip()
    else:
        raise ValueError("answer has no recognized value")

    evidence_values = _string_list(raw.get("evidence", []), "evidence")
    evidence: list[EvidenceLink] = []
    for item in evidence_values:
        location = paragraph_locations.get(item)
        if location is None:
            start = document_text.find(item)
            if start < 0:
                raise ValueError("evidence text is not present in the document")
            location = (start, start + len(item), "unknown", -1)
        evidence.append(
            EvidenceLink(
                text=item,
                start=location[0],
                end=location[1],
                section=location[2],
                paragraph_index=location[3],
            )
        )
    return AnswerRecord(text=text, answer_type=answer_type, evidence=tuple(evidence))


def _render_document(
    title: str,
    abstract: list[str],
    section_names: list[str],
    paragraphs_by_section: list[list[str]],
) -> tuple[str, dict[str, tuple[int, int, str, int]]]:
    chunks = [title, "Abstract", *abstract]
    locations: dict[str, tuple[int, int, str, int]] = {}
    text = "\n\n".join(chunks)
    for section, paragraphs in zip(section_names, paragraphs_by_section, strict=True):
        text += f"\n\n{section}"
        for index, paragraph in enumerate(paragraphs):
            text += "\n\n"
            start = len(text)
            text += paragraph
            locations.setdefault(paragraph, (start, len(text), section, index))
    return text, locations


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")
    return cast(dict[str, Any], value)


def _list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list")
    return cast(list[Any], value)


def _string(raw: dict[str, Any], key: str) -> str:
    value = raw[key]
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{key} must be a non-empty string")
    return value


def _string_list(value: Any, name: str) -> list[str]:
    values = _list(value, name)
    if not all(isinstance(item, str) for item in values):
        raise TypeError(f"{name} must contain strings")
    return cast(list[str], values)


def _nested_string_list(value: Any, name: str) -> list[list[str]]:
    values = _list(value, name)
    return [_string_list(item, name) for item in values]
