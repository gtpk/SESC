from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ism.inference.cache import CompressionCacheKey
from ism.inference.disk_cache import ImmutableCompressionCache


def key(document_text: str = "document") -> CompressionCacheKey:
    return CompressionCacheKey(
        document_text=document_text,
        method="ism",
        budget=128,
        prompt_version="ism-v1",
        model_id="mock",
        model_revision="local",
        tokenizer_revision="local",
        decoding_config=(("temperature", "0"),),
    )


def test_p6_fun_001_document_is_compressed_once_for_many_questions(tmp_path: Path) -> None:
    cache = ImmutableCompressionCache(tmp_path)
    calls = 0

    def compute() -> str:
        nonlocal calls
        calls += 1
        return "compressed"

    values = [cache.get_or_compute(key(), compute) for _ in range(10)]

    assert values == ["compressed"] * 10
    assert calls == 1
    assert cache.stats.misses == 1
    assert cache.stats.hits == 9


def test_p6_fun_002_question_changes_do_not_change_compression_key() -> None:
    first = key().digest()
    second = key().digest()

    assert first == second


def test_p6_fun_003_different_document_text_is_isolated(tmp_path: Path) -> None:
    cache = ImmutableCompressionCache(tmp_path)

    first = cache.get_or_compute(key("first"), lambda: "one")
    second = cache.get_or_compute(key("second"), lambda: "two")
    shared = cache.get_or_compute(key("first"), lambda: "should-not-run")

    assert (first, second, shared) == ("one", "two", "one")
    assert cache.stats.writes == 2


def test_p6_res_001_corrupt_checksum_is_recomputed(tmp_path: Path) -> None:
    cache = ImmutableCompressionCache(tmp_path)
    cache.get_or_compute(key(), lambda: "original")
    path = tmp_path / f"{key().digest()}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["value"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")

    restored = cache.get_or_compute(key(), lambda: "recomputed")

    assert restored == "recomputed"
    assert cache.stats.corruptions == 1
    assert cache.stats.writes == 2
    assert (tmp_path / f"{key().digest()}.corrupt").exists()


def test_p6_res_002_concurrent_writers_create_one_valid_entry(tmp_path: Path) -> None:
    cache = ImmutableCompressionCache(tmp_path)
    calls = 0
    calls_lock = threading.Lock()

    def compute() -> str:
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.01)
        return "shared"

    def worker(_: int) -> str:
        return cache.get_or_compute(key(), compute)

    with ThreadPoolExecutor(max_workers=8) as executor:
        values = list(executor.map(worker, range(16)))

    assert values == ["shared"] * 16
    assert calls == 1
    assert cache.stats.writes == 1
    assert cache.stats.hits == 15
