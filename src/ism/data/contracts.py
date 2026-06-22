from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AnswerType(StrEnum):
    EXTRACTIVE = "extractive"
    ABSTRACTIVE = "abstractive"
    YES_NO = "yes_no"
    UNANSWERABLE = "unanswerable"
    CLASSIFICATION = "classification"
    BOOLEAN = "boolean"


@dataclass(frozen=True)
class EvidenceLink:
    text: str
    start: int
    end: int
    section: str
    paragraph_index: int


@dataclass(frozen=True)
class AnswerRecord:
    text: str
    answer_type: AnswerType
    evidence: tuple[EvidenceLink, ...]


@dataclass(frozen=True)
class QuestionRecord:
    question_id: str
    document_id: str
    question: str
    answers: tuple[AnswerRecord, ...]


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    split: str
    title: str
    abstract: str
    document_text: str
    questions: tuple[QuestionRecord, ...]
