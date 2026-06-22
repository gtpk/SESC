from __future__ import annotations

from ism.data.rules import Condition, ConditionOperator, Fact, Rule, RuleGraph, RuleKind


def render_graph(graph: RuleGraph) -> str:
    lines = ["Facts:"]
    lines.extend(f"- {render_fact(fact)}." for fact in graph.initial_facts)
    lines.append("Rules:")
    lines.extend(f"- {render_rule(rule)}" for rule in graph.rules)
    return "\n".join(lines)


def render_fact(fact: Fact) -> str:
    time = f" at time {fact.timestamp}" if fact.timestamp is not None else ""
    return f"{fact.entity} has {fact.attribute} = {fact.value}{time}"


def render_rule(rule: Rule) -> str:
    conditions = [render_condition(item) for item in rule.conditions]
    if rule.kind is RuleKind.DISJUNCTION:
        premise = " or ".join(conditions)
    elif rule.kind is RuleKind.THRESHOLD:
        premise = f"at least {rule.threshold} of ({'; '.join(conditions)})"
    else:
        premise = " and ".join(conditions)

    prefix = ""
    if rule.kind is RuleKind.EXCEPTION:
        prefix = f"Exception to {rule.exception_of}: "
    elif rule.kind is RuleKind.PRECEDENCE:
        prefix = f"Priority {rule.priority}: "
    return f"{prefix}If {premise}, then {render_fact(rule.conclusion)}."


def render_condition(condition: Condition) -> str:
    if condition.operator is ConditionOperator.BEFORE:
        return (
            f"{condition.entity}.{condition.attribute} occurs before "
            f"{condition.reference_entity}.{condition.reference_attribute}"
        )
    operator = {
        ConditionOperator.EQUALS: "=",
        ConditionOperator.GTE: ">=",
        ConditionOperator.LTE: "<=",
    }[condition.operator]
    return f"{condition.entity}.{condition.attribute} {operator} {condition.value}"
