from __future__ import annotations

from ism.data.generator import GeneratedDocument, SyntheticGenerator
from ism.experiments.conditions import build_condition_matrix
from ism.experiments.diagnostics import (
    analyze_isms,
    corruption_strength,
    definition_self_containment,
    majority_baseline,
    relations_structure_score,
)
from ism.representation.models import ISMRepresentation, SymbolDefinition
from ism.representation.tokenizer import WhitespaceTokenCounter


def _gold_isms(n: int = 5) -> tuple[tuple[GeneratedDocument, ...], list[ISMRepresentation]]:
    docs = SyntheticGenerator(42).generate(n, split="dev")
    matrix = build_condition_matrix(
        docs,
        conditions=("full_context", "full_symbol_dict"),
        budget=128,
        seed=42,
        tokenizer=WhitespaceTokenCounter(),
    )
    reps: list[ISMRepresentation] = [
        record.representation
        for record in matrix.compressions
        if record.method == "ism" and record.representation is not None
    ]
    return docs, reps


def test_corruption_preserves_content_for_self_contained_defs() -> None:
    _, reps = _gold_isms(3)
    strength = corruption_strength(reps[0], seed=42)
    # Derangement only permutes labels; the definition multiset is unchanged and
    # answer tokens survive -> corruption does not change answerable content.
    assert strength.definitions_multiset_preserved is True
    assert strength.answer_tokens_preserved is True


def test_gold_relations_carry_no_structure() -> None:
    _, reps = _gold_isms(3)
    # Gold relations are a bare label list ("Z1 Z2 ...").
    assert relations_structure_score(reps[0]) == 0.0


def test_structured_relations_score_positive() -> None:
    rep = ISMRepresentation(
        symbols=("Z1", "Z2", "Z3"),
        dictionary=(
            SymbolDefinition(label="Z1", definition="marker a high"),
            SymbolDefinition(label="Z2", definition="marker b low"),
            SymbolDefinition(label="Z3", definition="repair high"),
        ),
        relations=("Z1 & Z2 -> Z3",),
    )
    assert relations_structure_score(rep) == 1.0


def test_gold_definitions_are_self_contained() -> None:
    _, reps = _gold_isms(3)
    # Each gold definition states a conclusion (risk = HIGH/MEDIUM/LOW, etc.).
    assert definition_self_containment(reps[0]) > 0.5


def test_majority_baseline_reports_per_type() -> None:
    docs, _ = _gold_isms(20)
    baseline = majority_baseline(docs)
    assert set(baseline) == {"classification", "boolean"}
    assert all(0.0 < value <= 1.0 for value in baseline.values())


def test_analyze_isms_aggregates() -> None:
    _, reps = _gold_isms(5)
    report = analyze_isms(reps, seed=42)
    assert report.documents == 5
    assert report.corruption_preserves_content == 1.0  # gold: always preserved
    assert report.mean_relations_structure == 0.0  # gold: no structure
