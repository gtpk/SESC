from __future__ import annotations

import random
from dataclasses import dataclass

from ism.data.contracts import AnswerRecord, AnswerType, QuestionRecord
from ism.data.render import render_graph
from ism.data.rules import (
    Condition,
    ConditionOperator,
    ExecutionResult,
    Fact,
    Rule,
    RuleExecutor,
    RuleGraph,
    RuleKind,
)


@dataclass(frozen=True)
class GeneratedQuestion:
    question_id: str
    document_id: str
    question: str
    answer: str
    answer_type: str
    required_rule_ids: tuple[str, ...]
    ood_type: str | None = None

    def to_record(self) -> QuestionRecord:
        answer_type = {
            "classification": AnswerType.CLASSIFICATION,
            "boolean": AnswerType.BOOLEAN,
        }[self.answer_type]
        return QuestionRecord(
            question_id=self.question_id,
            document_id=self.document_id,
            question=self.question,
            answers=(
                AnswerRecord(
                    text=self.answer,
                    answer_type=answer_type,
                    evidence=(),
                ),
            ),
        )


@dataclass(frozen=True)
class GeneratedDocument:
    document_id: str
    split: str
    document_text: str
    graph: RuleGraph
    questions: tuple[GeneratedQuestion, ...]
    generator_version: str
    seed: int


class SyntheticGenerator:
    VERSION = "0.1.0"

    def __init__(
        self,
        seed: int,
        *,
        document_min_tokens: int | None = None,
        document_max_tokens: int | None = None,
    ) -> None:
        if (document_min_tokens is None) != (document_max_tokens is None):
            raise ValueError("document_min_tokens and document_max_tokens must be set together")
        if (
            document_min_tokens is not None
            and document_max_tokens is not None
            and document_min_tokens > document_max_tokens
        ):
            raise ValueError("document_min_tokens must not exceed document_max_tokens")
        self._seed = seed
        self._document_min_tokens = document_min_tokens
        self._document_max_tokens = document_max_tokens

    def generate(self, count: int, *, split: str = "dev") -> tuple[GeneratedDocument, ...]:
        if count < 1:
            raise ValueError("count must be positive")
        rng = random.Random(self._seed)
        return tuple(self._generate_one(index, split, rng) for index in range(count))

    def _generate_one(
        self,
        index: int,
        split: str,
        rng: random.Random,
    ) -> GeneratedDocument:
        document_id = f"syn_{split}_{index:06d}"
        entity = f"case_{rng.randrange(10_000):04d}"
        marker_a = rng.choice(["high", "low"])
        marker_b = rng.choice(["high", "low"])
        repair = round(rng.random(), 2)
        facts = (
            Fact(entity=entity, attribute="marker_a", value=marker_a),
            Fact(entity=entity, attribute="marker_b", value=marker_b),
            Fact(entity=entity, attribute="repair_score", value=repair),
            Fact(entity=entity, attribute="event_a", value=True, timestamp=1),
            Fact(entity=entity, attribute="event_b", value=True, timestamp=2),
        )
        rules = (
            Rule(
                rule_id="r_conjunction",
                kind=RuleKind.CONJUNCTION,
                conditions=(
                    Condition(entity=entity, attribute="marker_a", value="high"),
                    Condition(entity=entity, attribute="marker_b", value="low"),
                ),
                conclusion=Fact(entity=entity, attribute="risk", value="HIGH"),
                priority=10,
            ),
            Rule(
                rule_id="r_disjunction",
                kind=RuleKind.DISJUNCTION,
                conditions=(
                    Condition(entity=entity, attribute="marker_a", value="low"),
                    Condition(entity=entity, attribute="marker_b", value="high"),
                ),
                conclusion=Fact(entity=entity, attribute="risk", value="MEDIUM"),
                priority=5,
            ),
            Rule(
                rule_id="r_threshold",
                kind=RuleKind.THRESHOLD,
                conditions=(
                    Condition(entity=entity, attribute="marker_a", value="high"),
                    Condition(entity=entity, attribute="marker_b", value="high"),
                    Condition(
                        entity=entity,
                        attribute="repair_score",
                        operator=ConditionOperator.GTE,
                        value=0.5,
                    ),
                ),
                threshold=2,
                conclusion=Fact(entity=entity, attribute="review", value=True),
            ),
            Rule(
                rule_id="r_temporal",
                kind=RuleKind.TEMPORAL,
                conditions=(
                    Condition(
                        entity=entity,
                        attribute="event_a",
                        operator=ConditionOperator.BEFORE,
                        value=True,
                        reference_entity=entity,
                        reference_attribute="event_b",
                    ),
                ),
                conclusion=Fact(entity=entity, attribute="ordered", value=True),
            ),
            Rule(
                rule_id="r_repair_exception",
                kind=RuleKind.EXCEPTION,
                exception_of="r_conjunction",
                conditions=(
                    Condition(
                        entity=entity,
                        attribute="repair_score",
                        operator=ConditionOperator.GTE,
                        value=0.8,
                    ),
                ),
                conclusion=Fact(entity=entity, attribute="risk", value="LOW"),
                priority=100,
            ),
            Rule(
                rule_id="r_precedence",
                kind=RuleKind.PRECEDENCE,
                conditions=(
                    Condition(entity=entity, attribute="marker_a", value="high"),
                    Condition(entity=entity, attribute="marker_b", value="high"),
                ),
                conclusion=Fact(entity=entity, attribute="risk", value="HIGH"),
                priority=20,
            ),
        )
        graph = RuleGraph(graph_id=document_id, initial_facts=facts, rules=rules)
        result = RuleExecutor().execute(graph)
        risk = _answer(result, entity, "risk", default="LOW")
        review = _answer(result, entity, "review", default=False)
        questions = (
            GeneratedQuestion(
                question_id=f"{document_id}_q00",
                document_id=document_id,
                question=f"What is the risk level for {entity}?",
                answer=str(risk),
                answer_type="classification",
                required_rule_ids=result.fired_rule_ids,
            ),
            GeneratedQuestion(
                question_id=f"{document_id}_q01",
                document_id=document_id,
                question=f"Does {entity} require review?",
                answer=str(review),
                answer_type="boolean",
                required_rule_ids=result.fired_rule_ids,
            ),
        )
        document_text = render_graph(graph)
        if self._document_min_tokens is not None and self._document_max_tokens is not None:
            document_text = self._with_filler(document_text, index)

        return GeneratedDocument(
            document_id=document_id,
            split=split,
            document_text=document_text,
            graph=graph,
            questions=questions,
            generator_version=self.VERSION,
            seed=self._seed,
        )

    def _with_filler(self, document_text: str, index: int) -> str:
        """Pad the document with deterministic neutral distractor text.

        Uses a dedicated per-document RNG seeded by (seed, index) so the rule
        graph, questions, and gold answers are byte-identical to the no-filler
        generation — only the surface text grows. Filler never asserts a
        risk/review/ordered conclusion, so it cannot change the answer.
        """
        assert self._document_min_tokens is not None
        assert self._document_max_tokens is not None
        rng = random.Random((self._seed + 1) * 2_654_435_761 + index)
        target = rng.randint(self._document_min_tokens, self._document_max_tokens)
        lines = [document_text, "Context notes:"]
        words = len(document_text.split()) + 2
        topics = (
            "telemetry", "logistics", "weather", "inventory", "maintenance",
            "billing", "scheduling", "network", "calibration", "shipping",
        )
        while words < target:
            sentence = (
                f"- Note {rng.randrange(100000):05d}: {rng.choice(topics)} channel "
                f"reading {rng.randrange(1000)} measured at {round(rng.random(), 3)} "
                "with nominal status and no escalation."
            )
            cost = len(sentence.split())
            if words + cost > self._document_max_tokens:
                break
            lines.append(sentence)
            words += cost
        return "\n".join(lines)


def _answer(
    result: ExecutionResult,
    entity: str,
    attribute: str,
    *,
    default: str | bool,
) -> str | bool:
    fact = result.get(entity, attribute)
    return default if fact is None else fact.value  # type: ignore[return-value]
