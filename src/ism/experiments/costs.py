from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReuseCost:
    compression_calls: int
    compression_input_tokens: int
    compression_output_tokens: int
    reasoning_input_tokens: int
    reasoning_output_tokens: int
    serving_total_tokens: int
    end_to_end_total_tokens: int


def calculate_reuse_cost(
    *,
    document_tokens: int,
    representation_tokens: int,
    question_tokens: tuple[int, ...],
    answer_tokens: tuple[int, ...],
    compressed: bool,
) -> ReuseCost:
    if min(document_tokens, representation_tokens, *question_tokens, *answer_tokens) < 0:
        raise ValueError("token counts must not be negative")
    if len(question_tokens) != len(answer_tokens):
        raise ValueError("question and answer token counts must align")

    context_tokens = representation_tokens if compressed else document_tokens
    reasoning_input = sum(context_tokens + question for question in question_tokens)
    reasoning_output = sum(answer_tokens)
    compression_calls = 1 if compressed else 0
    compression_input = document_tokens if compressed else 0
    compression_output = representation_tokens if compressed else 0
    serving_total = reasoning_input + reasoning_output
    end_to_end = serving_total + compression_input + compression_output
    return ReuseCost(
        compression_calls=compression_calls,
        compression_input_tokens=compression_input,
        compression_output_tokens=compression_output,
        reasoning_input_tokens=reasoning_input,
        reasoning_output_tokens=reasoning_output,
        serving_total_tokens=serving_total,
        end_to_end_total_tokens=end_to_end,
    )
