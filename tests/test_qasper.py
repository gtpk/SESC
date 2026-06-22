from __future__ import annotations

from copy import deepcopy
from typing import cast

import pytest

from ism.data.contracts import AnswerType
from ism.data.qasper import QasperAdapter, stable_adapter_digest


def paper(question_count: int = 4) -> dict[str, object]:
    answer_templates: tuple[dict[str, object], ...] = (
        {
            "unanswerable": False,
            "yes_no": True,
            "extractive_spans": [],
            "free_form_answer": "",
            "evidence": ["The method improves accuracy."],
        },
        {
            "unanswerable": False,
            "yes_no": None,
            "extractive_spans": ["accuracy"],
            "free_form_answer": "",
            "evidence": ["The method improves accuracy."],
        },
        {
            "unanswerable": True,
            "yes_no": None,
            "extractive_spans": [],
            "free_form_answer": "",
            "evidence": [],
        },
        {
            "unanswerable": False,
            "yes_no": None,
            "extractive_spans": [],
            "free_form_answer": "It uses a compact encoder.",
            "evidence": ["A compact encoder is used."],
        },
    )
    return {
        "title": "A Paper",
        "abstract": ["An abstract."],
        "full_text": {
            "section_name": ["Introduction", "Method"],
            "paragraphs": [
                ["The method improves accuracy."],
                ["A compact encoder is used."],
            ],
        },
        "qas": [
            {
                "question_id": f"q{index:02d}",
                "question": f"Question {index}?",
                "answers": [{"answer": deepcopy(answer_templates[index % 4])}],
            }
            for index in range(question_count)
        ],
    }


def test_p8_con_001_source_schema_maps_without_losing_core_fields() -> None:
    result = QasperAdapter().load({"paper-1": paper()}, split="dev")
    document = result.documents[0]

    assert result.quarantine == ()
    assert document.document_id == "paper-1"
    assert document.title == "A Paper"
    assert document.abstract == "An abstract."
    assert len(document.questions) == 4
    assert document.questions[0].document_id == "paper-1"


def test_p8_con_002_ids_are_stable_across_reload() -> None:
    adapter = QasperAdapter()
    first = adapter.load({"paper-1": paper()}, split="dev")
    second = adapter.load({"paper-1": deepcopy(paper())}, split="dev")

    assert [item.document_id for item in first.documents] == [
        item.document_id for item in second.documents
    ]
    assert [item.question_id for item in first.documents[0].questions] == [
        item.question_id for item in second.documents[0].questions
    ]
    assert stable_adapter_digest(first) == stable_adapter_digest(second)


def test_p8_fun_001_answer_types_are_normalized() -> None:
    questions = QasperAdapter().load({"paper-1": paper()}, split="dev").documents[0].questions

    assert [item.answers[0].answer_type for item in questions] == [
        AnswerType.YES_NO,
        AnswerType.EXTRACTIVE,
        AnswerType.UNANSWERABLE,
        AnswerType.ABSTRACTIVE,
    ]
    assert [item.answers[0].text for item in questions] == [
        "Yes",
        "accuracy",
        "Unanswerable",
        "It uses a compact encoder.",
    ]


def test_p8_fun_002_evidence_preserves_source_offset_and_section() -> None:
    document = QasperAdapter().load({"paper-1": paper()}, split="dev").documents[0]
    evidence = document.questions[0].answers[0].evidence[0]

    assert document.document_text[evidence.start : evidence.end] == evidence.text
    assert evidence.section == "Introduction"
    assert evidence.paragraph_index == 0


def test_p8_err_001_malformed_question_is_quarantined_without_stopping_load() -> None:
    raw = paper()
    qas = cast(list[object], raw["qas"])
    qas.append({"question_id": "broken", "answers": []})

    result = QasperAdapter().load({"paper-1": raw}, split="dev")

    assert len(result.documents) == 1
    assert len(result.documents[0].questions) == 4
    assert len(result.quarantine) == 1
    assert result.quarantine[0].document_id == "paper-1"


def test_p8_cfg_001_test_split_tuning_is_rejected() -> None:
    with pytest.raises(ValueError, match="test split"):
        QasperAdapter().load({"paper-1": paper()}, split="test", tuning_mode=True)


def test_p8_reg_001_twenty_question_golden_digest() -> None:
    result = QasperAdapter().load({"paper-1": paper(question_count=20)}, split="dev")

    assert len(result.documents[0].questions) == 20
    assert stable_adapter_digest(result) == (
        "3036aaf34ac7274e66de890c86ed5683c0e8a4816b1a7a9dc14f15f4ad2d60af"
    )
