from __future__ import annotations

from ism.experiments.costs import calculate_reuse_cost


def test_p6_fun_004_cost_formula_matches_hand_calculation() -> None:
    cost = calculate_reuse_cost(
        document_tokens=1000,
        representation_tokens=100,
        question_tokens=(10, 20, 30),
        answer_tokens=(2, 2, 2),
        compressed=True,
    )

    assert cost.compression_calls == 1
    assert cost.compression_input_tokens == 1000
    assert cost.compression_output_tokens == 100
    assert cost.reasoning_input_tokens == 360
    assert cost.reasoning_output_tokens == 6
    assert cost.serving_total_tokens == 366
    assert cost.end_to_end_total_tokens == 1466


def test_p6_con_001_serving_and_end_to_end_costs_are_distinct() -> None:
    compressed = calculate_reuse_cost(
        document_tokens=1000,
        representation_tokens=100,
        question_tokens=(10,),
        answer_tokens=(2,),
        compressed=True,
    )
    full = calculate_reuse_cost(
        document_tokens=1000,
        representation_tokens=100,
        question_tokens=(10,),
        answer_tokens=(2,),
        compressed=False,
    )

    assert compressed.serving_total_tokens == 112
    assert compressed.end_to_end_total_tokens == 1212
    assert full.serving_total_tokens == full.end_to_end_total_tokens == 1012


def test_p6_reg_001_question_order_does_not_change_cost() -> None:
    first = calculate_reuse_cost(
        document_tokens=1000,
        representation_tokens=100,
        question_tokens=(10, 20, 30),
        answer_tokens=(1, 2, 3),
        compressed=True,
    )
    second = calculate_reuse_cost(
        document_tokens=1000,
        representation_tokens=100,
        question_tokens=(30, 10, 20),
        answer_tokens=(3, 1, 2),
        compressed=True,
    )

    assert first == second
