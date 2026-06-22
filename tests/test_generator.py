from __future__ import annotations

import hashlib
import json

from ism.data.contracts import AnswerType, QuestionRecord
from ism.data.generator import SyntheticGenerator
from ism.data.render import render_graph
from ism.data.rules import RuleKind


def test_p1_det_001_same_seed_is_byte_identical() -> None:
    first = SyntheticGenerator(42).generate(10)
    second = SyntheticGenerator(42).generate(10)

    assert first == second


def test_p1_det_002_different_seed_changes_documents() -> None:
    first = SyntheticGenerator(42).generate(10)
    second = SyntheticGenerator(43).generate(10)

    assert first != second


def test_p1_con_002_document_and_question_ids_are_unique() -> None:
    documents = SyntheticGenerator(42).generate(100)
    document_ids = [item.document_id for item in documents]
    question_ids = [
        question.question_id for document in documents for question in document.questions
    ]

    assert len(document_ids) == len(set(document_ids))
    assert len(question_ids) == len(set(question_ids))


def test_generated_questions_are_determined() -> None:
    documents = SyntheticGenerator(42).generate(100)

    assert all(question.answer != "" for item in documents for question in item.questions)
    assert all(item.document_text for item in documents)


def test_p1_con_003_generator_covers_every_rule_kind() -> None:
    document = SyntheticGenerator(42).generate(1)[0]

    assert {rule.kind for rule in document.graph.rules} == set(RuleKind)


def test_p1_reg_001_golden_graphs_and_answers() -> None:
    documents = SyntheticGenerator(42).generate(50)
    graph_payload = "\n".join(document.graph.stable_json() for document in documents[:20]).encode()
    answer_payload = json.dumps(
        [question.answer for document in documents for question in document.questions],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()

    assert hashlib.sha256(graph_payload).hexdigest() == (
        "8ace7e76a035b6186fb11115ea76de1611a9b1f1957abc7dc6e56dcdbfeca5e4"
    )
    assert hashlib.sha256(answer_payload).hexdigest() == (
        "3fe1e4ba5e6f007516b7881f03bce1d6a57c7e4daaadd9cbcbb2d3ff24d62feb"
    )


def test_renderer_does_not_mutate_graph() -> None:
    graph = SyntheticGenerator(42).generate(1)[0].graph
    before = graph.stable_json()

    rendered = render_graph(graph)

    assert rendered
    assert graph.stable_json() == before


def test_synthetic_questions_use_common_question_record_contract() -> None:
    question = SyntheticGenerator(42).generate(1)[0].questions[0]

    record = question.to_record()

    assert isinstance(record, QuestionRecord)
    assert record.answers[0].answer_type is AnswerType.CLASSIFICATION
