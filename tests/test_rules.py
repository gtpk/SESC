from __future__ import annotations

import pytest
from pydantic import ValidationError

from ism.data.rules import (
    Condition,
    ConditionOperator,
    Fact,
    Rule,
    RuleConflictError,
    RuleCycleError,
    RuleExecutor,
    RuleGraph,
    RuleKind,
    RuleValidationError,
)


def execute(*facts: Fact, rules: tuple[Rule, ...]) -> dict[tuple[str, str], object]:
    result = RuleExecutor().execute(RuleGraph(graph_id="fixture", initial_facts=facts, rules=rules))
    return {fact.key: fact.value for fact in result.facts}


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (True, True, True),
        (True, False, None),
        (False, True, None),
        (False, False, None),
    ],
)
def test_p1_fun_001_conjunction_truth_table(
    a: bool,
    b: bool,
    expected: bool | None,
) -> None:
    entity = "case"
    rule = Rule(
        rule_id="and",
        kind=RuleKind.CONJUNCTION,
        conditions=(
            Condition(entity=entity, attribute="a", value=True),
            Condition(entity=entity, attribute="b", value=True),
        ),
        conclusion=Fact(entity=entity, attribute="out", value=True),
    )

    state = execute(
        Fact(entity=entity, attribute="a", value=a),
        Fact(entity=entity, attribute="b", value=b),
        rules=(rule,),
    )

    assert state.get((entity, "out")) == expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (True, True, True),
        (True, False, True),
        (False, True, True),
        (False, False, None),
    ],
)
def test_p1_fun_002_disjunction_truth_table(
    a: bool,
    b: bool,
    expected: bool | None,
) -> None:
    entity = "case"
    rule = Rule(
        rule_id="or",
        kind=RuleKind.DISJUNCTION,
        conditions=(
            Condition(entity=entity, attribute="a", value=True),
            Condition(entity=entity, attribute="b", value=True),
        ),
        conclusion=Fact(entity=entity, attribute="out", value=True),
    )

    state = execute(
        Fact(entity=entity, attribute="a", value=a),
        Fact(entity=entity, attribute="b", value=b),
        rules=(rule,),
    )

    assert state.get((entity, "out")) == expected


def test_p1_fun_003_exception_suppresses_target_rule() -> None:
    entity = "case"
    base = Rule(
        rule_id="base",
        kind=RuleKind.CONJUNCTION,
        conditions=(Condition(entity=entity, attribute="marker", value="high"),),
        conclusion=Fact(entity=entity, attribute="risk", value="HIGH"),
    )
    exception = Rule(
        rule_id="repair_exception",
        kind=RuleKind.EXCEPTION,
        exception_of="base",
        conditions=(
            Condition(
                entity=entity,
                attribute="repair",
                operator=ConditionOperator.GTE,
                value=0.8,
            ),
        ),
        conclusion=Fact(entity=entity, attribute="risk", value="LOW"),
        priority=100,
    )

    state = execute(
        Fact(entity=entity, attribute="marker", value="high"),
        Fact(entity=entity, attribute="repair", value=0.9),
        rules=(base, exception),
    )

    assert state[(entity, "risk")] == "LOW"


def test_p1_fun_003_exception_can_suppress_another_exception() -> None:
    entity = "case"
    base = Rule(
        rule_id="base",
        kind=RuleKind.CONJUNCTION,
        conditions=(Condition(entity=entity, attribute="marker", value="high"),),
        conclusion=Fact(entity=entity, attribute="risk", value="HIGH"),
    )
    exception = Rule(
        rule_id="repair_exception",
        kind=RuleKind.EXCEPTION,
        exception_of="base",
        conditions=(Condition(entity=entity, attribute="repair", value=True),),
        conclusion=Fact(entity=entity, attribute="risk", value="LOW"),
        priority=100,
    )
    exception_to_exception = Rule(
        rule_id="repair_invalid",
        kind=RuleKind.EXCEPTION,
        exception_of="repair_exception",
        conditions=(Condition(entity=entity, attribute="repair_invalid", value=True),),
        conclusion=Fact(entity=entity, attribute="risk", value="HIGH"),
        priority=200,
    )

    state = execute(
        Fact(entity=entity, attribute="marker", value="high"),
        Fact(entity=entity, attribute="repair", value=True),
        Fact(entity=entity, attribute="repair_invalid", value=True),
        rules=(base, exception, exception_to_exception),
    )

    assert state[(entity, "risk")] == "HIGH"


def test_p1_fun_004_equal_priority_conflict_is_rejected() -> None:
    entity = "case"
    condition = (Condition(entity=entity, attribute="marker", value=True),)
    graph = RuleGraph(
        graph_id="conflict",
        initial_facts=(Fact(entity=entity, attribute="marker", value=True),),
        rules=(
            Rule(
                rule_id="a",
                kind=RuleKind.PRECEDENCE,
                conditions=condition,
                conclusion=Fact(entity=entity, attribute="risk", value="HIGH"),
                priority=10,
            ),
            Rule(
                rule_id="b",
                kind=RuleKind.PRECEDENCE,
                conditions=condition,
                conclusion=Fact(entity=entity, attribute="risk", value="LOW"),
                priority=10,
            ),
        ),
    )

    with pytest.raises(RuleConflictError, match="share priority"):
        RuleExecutor().execute(graph)


@pytest.mark.parametrize(
    ("true_count", "expected"),
    [(1, None), (2, True), (3, True)],
)
def test_p1_fun_005_threshold_boundary(
    true_count: int,
    expected: bool | None,
) -> None:
    entity = "case"
    facts = tuple(
        Fact(entity=entity, attribute=f"m{index}", value=index < true_count) for index in range(3)
    )
    rule = Rule(
        rule_id="threshold",
        kind=RuleKind.THRESHOLD,
        threshold=2,
        conditions=tuple(
            Condition(entity=entity, attribute=f"m{index}", value=True) for index in range(3)
        ),
        conclusion=Fact(entity=entity, attribute="out", value=True),
    )

    state = execute(*facts, rules=(rule,))

    assert state.get((entity, "out")) == expected


def test_p1_fun_006_temporal_ordering_changes_result() -> None:
    entity = "case"
    temporal = Rule(
        rule_id="temporal",
        kind=RuleKind.TEMPORAL,
        conditions=(
            Condition(
                entity=entity,
                attribute="start",
                operator=ConditionOperator.BEFORE,
                value=True,
                reference_entity=entity,
                reference_attribute="finish",
            ),
        ),
        conclusion=Fact(entity=entity, attribute="ordered", value=True),
    )

    ordered = execute(
        Fact(entity=entity, attribute="start", value=True, timestamp=1),
        Fact(entity=entity, attribute="finish", value=True, timestamp=2),
        rules=(temporal,),
    )
    reversed_state = execute(
        Fact(entity=entity, attribute="start", value=True, timestamp=2),
        Fact(entity=entity, attribute="finish", value=True, timestamp=1),
        rules=(temporal,),
    )

    assert ordered[(entity, "ordered")] is True
    assert (entity, "ordered") not in reversed_state


def test_p1_err_002_dependency_cycle_is_rejected() -> None:
    entity = "case"
    graph = RuleGraph(
        graph_id="cycle",
        initial_facts=(Fact(entity=entity, attribute="a", value=True),),
        rules=(
            Rule(
                rule_id="a_to_b",
                kind=RuleKind.CONJUNCTION,
                conditions=(Condition(entity=entity, attribute="a", value=True),),
                conclusion=Fact(entity=entity, attribute="b", value=True),
            ),
            Rule(
                rule_id="b_to_a",
                kind=RuleKind.CONJUNCTION,
                conditions=(Condition(entity=entity, attribute="b", value=True),),
                conclusion=Fact(entity=entity, attribute="a", value=True),
            ),
        ),
    )

    with pytest.raises(RuleCycleError, match="dependency cycle"):
        RuleExecutor().execute(graph)


def test_p1_err_001_undecidable_numeric_graph_is_rejected() -> None:
    entity = "case"
    graph = RuleGraph(
        graph_id="invalid-numeric-comparison",
        initial_facts=(Fact(entity=entity, attribute="score", value="unknown"),),
        rules=(
            Rule(
                rule_id="numeric",
                kind=RuleKind.CONJUNCTION,
                conditions=(
                    Condition(
                        entity=entity,
                        attribute="score",
                        operator=ConditionOperator.GTE,
                        value=0.5,
                    ),
                ),
                conclusion=Fact(entity=entity, attribute="out", value=True),
            ),
        ),
    )

    with pytest.raises(RuleValidationError, match="numeric comparison requires"):
        RuleExecutor().execute(graph)


def test_p1_con_001_graph_round_trip() -> None:
    graph = RuleGraph(
        graph_id="roundtrip",
        initial_facts=(Fact(entity="case", attribute="a", value=True),),
        rules=(
            Rule(
                rule_id="rule",
                kind=RuleKind.CONJUNCTION,
                conditions=(Condition(entity="case", attribute="a", value=True),),
                conclusion=Fact(entity="case", attribute="b", value=True),
            ),
        ),
    )

    restored = RuleGraph.model_validate_json(graph.stable_json())

    assert restored == graph


def test_duplicate_initial_fact_keys_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        RuleGraph(
            graph_id="duplicate",
            initial_facts=(
                Fact(entity="case", attribute="a", value=True),
                Fact(entity="case", attribute="a", value=False),
            ),
            rules=(),
        )
