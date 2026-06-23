"""LLM-based ISM compressor (paper §3.3 main setup).

A fixed instruction-tuned model turns a document into the canonical inspectable
representation ([DICTIONARY]/[RELATIONS]). The raw output is parsed back into a
structured ISMRepresentation so the ablation interventions (remove/corrupt/
random/swap) can be applied. Budget violations and malformed output trigger
prompt-nudged regeneration, per §3.3 #5.
"""

from __future__ import annotations

from dataclasses import dataclass

from ism.data.generator import GeneratedDocument
from ism.experiments.diagnostics import definition_self_containment
from ism.inference.contracts import GenerationRequest, TextGenerator
from ism.representation.models import ISMRepresentation
from ism.representation.parser import ISMParseError, parse_ism
from ism.representation.tokenizer import TokenCounter


class CompressionError(RuntimeError):
    """Raised when a document could not be compressed into a valid ISM."""


@dataclass(frozen=True)
class CompressionOutcome:
    representation: ISMRepresentation
    attempts: int


def build_compression_prompt(document_text: str, *, budget: int, nudge: str | None = None) -> str:
    instruction = (
        "You compress the document below into an inspectable symbolic representation.\n"
        "Output ONLY these two sections and nothing else:\n"
        "[DICTIONARY]\n"
        "Z1 := short definition of a condition, rule, exception, or relation\n"
        "Z2 := ...\n"
        "[RELATIONS]\n"
        "one or more lines combining the symbols, e.g. Z1 Z2 !Z3\n\n"
        "Rules:\n"
        "- Every symbol label is the letter Z followed by a number (Z1, Z2, ...).\n"
        "- Each [DICTIONARY] line must be exactly: LABEL := definition.\n"
        "- Each definition must be self-contained: include BOTH the trigger "
        "condition(s) and the resulting conclusion/outcome.\n"
        "- Do not place the conclusion only in [RELATIONS]; every symbol definition "
        "must say what it implies, e.g. IF marker_a is high THEN risk = HIGH.\n"
        "- Preserve conditions, conclusions, exceptions, priorities, thresholds, "
        "and ordering.\n"
        "- Do NOT answer any question; produce a reusable representation.\n"
        f"- Keep the entire output within {budget} whitespace-separated tokens.\n"
    )
    if nudge:
        instruction += f"- Your previous output was rejected ({nudge}); fix it.\n"
    return f"{instruction}\nDocument:\n{document_text}\n"


class LlmCompressor:
    def __init__(
        self,
        generator: TextGenerator,
        *,
        tokenizer: TokenCounter,
        seed: int,
        max_attempts: int,
        max_new_tokens: int,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.generator = generator
        self.tokenizer = tokenizer
        self.seed = seed
        self.max_attempts = max_attempts
        self.max_new_tokens = max_new_tokens

    def compress(self, document: GeneratedDocument, *, budget: int) -> CompressionOutcome:
        nudge: str | None = None
        last_error = "no attempts"
        for attempt in range(self.max_attempts):
            request = GenerationRequest(
                request_id=f"{document.document_id}:compress:{attempt}",
                prompt=build_compression_prompt(document.document_text, budget=budget, nudge=nudge),
                max_new_tokens=self.max_new_tokens,
                seed=self.seed + attempt,
            )
            (result,) = self.generator.generate((request,))
            if not result.succeeded or result.text is None:
                last_error = result.error_message or "generation failed"
                nudge = last_error
                continue
            try:
                representation = parse_ism(
                    result.text,
                    budget=budget,
                    tokenizer=self.tokenizer,
                )
            except ISMParseError as error:
                last_error = error.code.value
                nudge = last_error
                continue
            containment = definition_self_containment(representation)
            if containment < 1.0:
                last_error = f"missing_conclusion_tokens: self_containment={containment:.2f}"
                nudge = (
                    "missing conclusions in one or more dictionary definitions; "
                    "rewrite every LABEL := line as a complete IF condition THEN outcome rule"
                )
                continue
            return CompressionOutcome(representation=representation, attempts=attempt + 1)
        raise CompressionError(
            f"{document.document_id}: no valid ISM after {self.max_attempts} attempts "
            f"(last: {last_error})"
        )


__all__ = [
    "CompressionError",
    "CompressionOutcome",
    "LlmCompressor",
    "build_compression_prompt",
]
