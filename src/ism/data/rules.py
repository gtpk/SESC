from __future__ import annotations

from collections import defaultdict
from enum import StrEnum
from typing import Annotated, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

Scalar: TypeAlias = str | int | float | bool


class RuleError(RuntimeError):
    """Base class for deterministic rule execution failures."""


class RuleConflictError(RuleError):
    """Raised when equally ranked rules derive conflicting values."""


class RuleCycleError(RuleError):
    """Raised when rule evaluation revisits a previous state."""


class RuleValidationError(RuleError):
    """Raised when a graph cannot be evaluated safely."""


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RuleKind(StrEnum):
    CONJUNCTION = "conjunction"
    DISJUNCTION = "disjunction"
    EXCEPTION = "exception"
    PRECEDENCE = "precedence"
    THRESHOLD = "threshold"
    TEMPORAL = "temporal"


class ConditionOperator(StrEnum):
    EQUALS = "equals"
    GTE = "gte"
    LTE = "lte"
    BEFORE = "before"


class Fact(FrozenModel):
    entity: Annotated[str, Field(min_length=1)]
    attribute: Annotated[str, Field(min_length=1)]
    value: Scalar
    timestamp: int | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.entity, self.attribute)


class Condition(FrozenModel):
    entity: Annotated[str, Field(min_length=1)]
    attribute: Annotated[str, Field(min_length=1)]
    operator: ConditionOperator = ConditionOperator.EQUALS
    value: Scalar
    reference_entity: str | None = None
    reference_attribute: str | None = None

    @model_validator(mode="after")
    def validate_temporal_reference(self) -> Condition:
        has_reference = self.reference_entity is not None or self.reference_attribute is not None
        if self.operator is ConditionOperator.BEFORE:
            if self.reference_entity is None or self.reference_attribute is None:
                raise ValueError("before condition requires reference entity and attribute")
        elif has_reference:
            raise ValueError("reference fields are only valid for before conditions")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return (self.entity, self.attribute)


class Rule(FrozenModel):
    rule_id: Annotated[str, Field(min_length=1)]
    kind: RuleKind
    conditions: Annotated[tuple[Condition, ...], Field(min_length=1)]
    conclusion: Fact
    priority: int = 0
    threshold: int | None = None
    exception_of: str | None = None

    @model_validator(mode="after")
    def validate_kind_contract(self) -> Rule:
        if self.kind is RuleKind.THRESHOLD:
            if self.threshold is None:
                raise ValueError("threshold rule requires threshold")
            if not 1 <= self.threshold <= len(self.conditions):
                raise ValueError("threshold must be within condition count")
        elif self.threshold is not None:
            raise ValueError("threshold is only valid for threshold rules")

        if self.kind is RuleKind.EXCEPTION:
            if self.exception_of is None:
                raise ValueError("exception rule requires exception_of")
        elif self.exception_of is not None:
            raise ValueError("exception_of is only valid for exception rules")

        if self.kind is RuleKind.TEMPORAL and not any(
            item.operator is ConditionOperator.BEFORE for item in self.conditions
        ):
            raise ValueError("temporal rule requires a before condition")
        return self


class RuleGraph(FrozenModel):
    graph_id: Annotated[str, Field(min_length=1)]
    initial_facts: tuple[Fact, ...]
    rules: tuple[Rule, ...]

    @model_validator(mode="after")
    def validate_graph_contract(self) -> RuleGraph:
        rule_ids = [item.rule_id for item in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rule IDs must be unique")

        known_ids = set(rule_ids)
        for rule in self.rules:
            if rule.exception_of is not None and rule.exception_of not in known_ids:
                raise ValueError(
                    f"exception {rule.rule_id} references unknown rule {rule.exception_of}"
                )

        fact_keys = [item.key for item in self.initial_facts]
        if len(fact_keys) != len(set(fact_keys)):
            raise ValueError("initial facts must not contain duplicate entity/attribute keys")
        return self

    def stable_json(self) -> str:
        return self.model_dump_json(indent=2)


class ExecutionResult(FrozenModel):
    graph_id: str
    facts: tuple[Fact, ...]
    fired_rule_ids: tuple[str, ...]
    iterations: int

    def get(self, entity: str, attribute: str) -> Fact | None:
        return next(
            (fact for fact in self.facts if fact.entity == entity and fact.attribute == attribute),
            None,
        )


class RuleExecutor:
    def execute(self, graph: RuleGraph, *, max_iterations: int = 100) -> ExecutionResult:
        if max_iterations < 1:
            raise ValueError("max_iterations must be positive")
        self._validate_dependency_cycles(graph)

        state = {fact.key: fact for fact in graph.initial_facts}
        seen_states: set[tuple[tuple[str, str, str, int | None], ...]] = set()
        fired: list[str] = []

        for iteration in range(1, max_iterations + 1):
            signature = self._state_signature(state)
            if signature in seen_states:
                raise RuleCycleError(f"graph {graph.graph_id} revisited a prior state")
            seen_states.add(signature)

            applicable = [rule for rule in graph.rules if self._applies(rule, state)]
            active_exception_targets = {
                rule.exception_of
                for rule in applicable
                if rule.kind is RuleKind.EXCEPTION and rule.exception_of is not None
            }
            candidates = [
                rule for rule in applicable if rule.rule_id not in active_exception_targets
            ]
            updates = self._select_updates(candidates)

            changed = False
            for rule in updates:
                previous = state.get(rule.conclusion.key)
                if previous != rule.conclusion:
                    state[rule.conclusion.key] = rule.conclusion
                    changed = True
                    fired.append(rule.rule_id)
            if not changed:
                return ExecutionResult(
                    graph_id=graph.graph_id,
                    facts=tuple(sorted(state.values(), key=lambda item: item.key)),
                    fired_rule_ids=tuple(fired),
                    iterations=iteration,
                )

        raise RuleCycleError(
            f"graph {graph.graph_id} did not converge within {max_iterations} iterations"
        )

    def _applies(
        self,
        rule: Rule,
        state: dict[tuple[str, str], Fact],
    ) -> bool:
        matches = [self._matches(condition, state) for condition in rule.conditions]
        if rule.kind is RuleKind.DISJUNCTION:
            return any(matches)
        if rule.kind is RuleKind.THRESHOLD:
            assert rule.threshold is not None
            return sum(matches) >= rule.threshold
        return all(matches)

    def _matches(
        self,
        condition: Condition,
        state: dict[tuple[str, str], Fact],
    ) -> bool:
        fact = state.get(condition.key)
        if fact is None:
            return False
        if condition.operator is ConditionOperator.EQUALS:
            return fact.value == condition.value
        if condition.operator is ConditionOperator.GTE:
            return _numeric(fact.value) >= _numeric(condition.value)
        if condition.operator is ConditionOperator.LTE:
            return _numeric(fact.value) <= _numeric(condition.value)
        if condition.operator is ConditionOperator.BEFORE:
            reference = state.get(
                (condition.reference_entity or "", condition.reference_attribute or "")
            )
            return (
                fact.timestamp is not None
                and reference is not None
                and reference.timestamp is not None
                and fact.timestamp < reference.timestamp
            )
        raise AssertionError(f"unsupported operator: {condition.operator}")

    def _select_updates(self, rules: list[Rule]) -> list[Rule]:
        grouped: dict[tuple[str, str], list[Rule]] = defaultdict(list)
        for rule in rules:
            grouped[rule.conclusion.key].append(rule)

        selected: list[Rule] = []
        for key, group in grouped.items():
            highest = max(rule.priority for rule in group)
            winners = [rule for rule in group if rule.priority == highest]
            values = {str(rule.conclusion.value) for rule in winners}
            if len(values) > 1:
                winner_ids = ", ".join(sorted(rule.rule_id for rule in winners))
                raise RuleConflictError(
                    f"conflicting rules for {key}: {winner_ids} share priority {highest}"
                )
            selected.append(sorted(winners, key=lambda item: item.rule_id)[0])
        return sorted(selected, key=lambda item: item.rule_id)

    def _validate_dependency_cycles(self, graph: RuleGraph) -> None:
        edges: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
        for rule in graph.rules:
            for condition in rule.conditions:
                edges[condition.key].add(rule.conclusion.key)

        visiting: set[tuple[str, str]] = set()
        visited: set[tuple[str, str]] = set()

        def visit(node: tuple[str, str]) -> None:
            if node in visiting:
                raise RuleCycleError(f"dependency cycle detected at {node}")
            if node in visited:
                return
            visiting.add(node)
            for target in edges.get(node, set()):
                visit(target)
            visiting.remove(node)
            visited.add(node)

        for node in tuple(edges):
            visit(node)

    def _state_signature(
        self,
        state: dict[tuple[str, str], Fact],
    ) -> tuple[tuple[str, str, str, int | None], ...]:
        return tuple(
            sorted(
                (
                    fact.entity,
                    fact.attribute,
                    repr(fact.value),
                    fact.timestamp,
                )
                for fact in state.values()
            )
        )


def _numeric(value: Scalar) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise RuleValidationError(f"numeric comparison requires int or float, got {value!r}")
    return float(value)
