"""Diagnostics for the Dictionary Ablation null result (Δmap ≈ 0).

Pure, GPU-free measurements that separate the candidate causes:
- is the dictionary *corruption* actually content-changing, or does it only
  permute labels of self-contained rules? (corruption_strength)
- do RELATIONS bind labels to logic, or are they a vacuous label list?
  (relations_structure_score)
- are definitions self-contained rules (answer derivable without the label
  binding)? (definition_self_containment)
- can the task be solved by a majority-class shortcut? (majority_baseline)

See docs/reviews/llm-ism-diagnostic.md.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from ism.data.generator import GeneratedDocument
from ism.data.render import render_rule
from ism.representation.interventions import corrupt_dictionary
from ism.representation.models import ISMRepresentation

# Answer-bearing tokens the synthetic task turns on.
ANSWER_TOKENS = ("high", "medium", "low", "true", "false")
# Operators / connectives that make a RELATIONS line carry logic rather than
# being a bare label list.
_STRUCTURE = re.compile(r"(->|=>|!|&|\||\bif\b|\bthen\b|\bunless\b|\bnot\b|\bor\b|\band\b)", re.I)
_TOKEN = re.compile(r"[a-z0-9_]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.casefold()))


@dataclass(frozen=True)
class CorruptionStrength:
    definitions_multiset_preserved: bool
    mean_per_label_overlap: float  # token Jaccard between orig and corrupted def per label
    answer_tokens_preserved: bool  # do answer tokens survive corruption (content intact)


def corruption_strength(representation: ISMRepresentation, *, seed: int) -> CorruptionStrength:
    """Quantify how much `corrupt_dictionary` actually changes answerable content."""
    corrupted = corrupt_dictionary(representation, seed=seed).representation
    orig_defs = [d.definition for d in representation.dictionary]
    corr_defs = [d.definition for d in corrupted.dictionary]

    overlaps: list[float] = []
    for orig, corr in zip(orig_defs, corr_defs, strict=True):
        a, b = _tokens(orig), _tokens(corr)
        union = a | b
        overlaps.append(len(a & b) / len(union) if union else 1.0)

    def _answer_tokens(defs: list[str]) -> set[str]:
        joined = " ".join(defs).casefold()
        return {t for t in ANSWER_TOKENS if t in joined}

    return CorruptionStrength(
        definitions_multiset_preserved=sorted(orig_defs) == sorted(corr_defs),
        mean_per_label_overlap=sum(overlaps) / len(overlaps) if overlaps else 1.0,
        answer_tokens_preserved=_answer_tokens(orig_defs) == _answer_tokens(corr_defs),
    )


def relations_structure_score(representation: ISMRepresentation) -> float:
    """Fraction of relation lines that contain a logic operator/connective.

    0.0 means relations are a bare label list (labels carry no logic, so
    relabeling via corruption cannot change the derivable answer).
    """
    if not representation.relations:
        return 0.0
    structured = sum(1 for line in representation.relations if _STRUCTURE.search(line))
    return structured / len(representation.relations)


def definition_self_containment(representation: ISMRepresentation) -> float:
    """Fraction of definitions that already contain an answer-bearing token.

    High values mean each definition is a self-contained rule, so the answer is
    derivable from definition *content* regardless of label binding.
    """
    if not representation.dictionary:
        return 0.0
    contained = 0
    for item in representation.dictionary:
        tokens = _tokens(item.definition)
        if any(token in tokens for token in ANSWER_TOKENS):
            contained += 1
    return contained / len(representation.dictionary)


def rule_coverage(
    document: GeneratedDocument,
    representation: ISMRepresentation,
    *,
    threshold: float = 0.5,
) -> float:
    """Fraction of gold rules represented by some ISM definition (purity).

    Each gold rule is rendered to its canonical text; a rule is "covered" if any
    dictionary definition shares at least `threshold` of the rule's tokens
    (Jaccard). Measures whether the compressor preserved the rules at all.
    """
    rules = document.graph.rules
    if not rules:
        return 1.0
    definition_tokens = [_tokens(item.definition) for item in representation.dictionary]
    covered = 0
    for rule in rules:
        rule_tokens = _tokens(render_rule(rule))
        if not rule_tokens:
            continue
        best = max(
            (len(rule_tokens & dt) / len(rule_tokens | dt) for dt in definition_tokens),
            default=0.0,
        )
        if best >= threshold:
            covered += 1
    return covered / len(rules)


def majority_baseline(documents: Sequence[GeneratedDocument]) -> dict[str, float]:
    """Per-answer-type majority-class accuracy (a shortcut lower bound)."""
    counts: dict[str, Counter[str]] = {}
    for document in documents:
        for question in document.questions:
            counts.setdefault(question.answer_type, Counter())[question.answer] += 1
    return {
        answer_type: max(counter.values()) / sum(counter.values())
        for answer_type, counter in counts.items()
    }


@dataclass(frozen=True)
class IsmStructureReport:
    documents: int
    mean_corruption_overlap: float
    corruption_preserves_content: float  # fraction of docs where defs multiset preserved
    mean_relations_structure: float
    mean_self_containment: float


def analyze_isms(
    representations: Sequence[ISMRepresentation],
    *,
    seed: int,
) -> IsmStructureReport:
    if not representations:
        raise ValueError("no representations to analyze")
    overlaps: list[float] = []
    preserved = 0
    structure: list[float] = []
    self_contained: list[float] = []
    for representation in representations:
        if len(representation.dictionary) >= 2:
            strength = corruption_strength(representation, seed=seed)
            overlaps.append(strength.mean_per_label_overlap)
            preserved += int(strength.definitions_multiset_preserved)
        structure.append(relations_structure_score(representation))
        self_contained.append(definition_self_containment(representation))
    n = len(representations)
    return IsmStructureReport(
        documents=n,
        mean_corruption_overlap=sum(overlaps) / len(overlaps) if overlaps else 1.0,
        corruption_preserves_content=preserved / len(overlaps) if overlaps else 1.0,
        mean_relations_structure=sum(structure) / n,
        mean_self_containment=sum(self_contained) / n,
    )


__all__ = [
    "ANSWER_TOKENS",
    "CorruptionStrength",
    "IsmStructureReport",
    "analyze_isms",
    "corruption_strength",
    "definition_self_containment",
    "majority_baseline",
    "relations_structure_score",
    "rule_coverage",
]
