from __future__ import annotations

from dataclasses import replace

from ism.inference.cache import CompressionCacheKey


def base_key() -> CompressionCacheKey:
    return CompressionCacheKey(
        document_text="document",
        method="ism",
        budget=128,
        prompt_version="ism-v1",
        model_id="mock",
        model_revision="rev-a",
        tokenizer_revision="tok-a",
        decoding_config=(("temperature", "0"),),
    )


def test_p3_cfg_001_cache_key_changes_for_every_semantic_input() -> None:
    original = base_key()

    variants = (
        replace(original, document_text="other"),
        replace(original, method="summary"),
        replace(original, budget=64),
        replace(original, prompt_version="ism-v2"),
        replace(original, model_id="other"),
        replace(original, model_revision="rev-b"),
        replace(original, tokenizer_revision="tok-b"),
        replace(original, decoding_config=(("temperature", "1"),)),
    )

    assert all(item.digest() != original.digest() for item in variants)


def test_p3_cfg_002_question_is_not_part_of_compression_cache_key() -> None:
    key = base_key()

    first_question = key.digest()
    second_question = key.digest()

    assert first_question == second_question
