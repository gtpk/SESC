from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ism.inference.cache import CompressionCacheKey


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    corruptions: int = 0
    writes: int = 0


class ImmutableCompressionCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.stats = CacheStats()

    def get_or_compute(
        self,
        key: CompressionCacheKey,
        compute: Callable[[], str],
    ) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        digest = key.digest()
        path = self.root / f"{digest}.json"
        lock_path = self.root / f"{digest}.lock"
        with lock_path.open("a+", encoding="utf-8") as lock_stream:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
            try:
                cached = self._read(path, expected_key=digest)
                if cached is not None:
                    self.stats.hits += 1
                    return cached
                self.stats.misses += 1
                value = compute()
                self._write(path, key_digest=digest, value=value)
                self.stats.writes += 1
                return value
            finally:
                fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)

    def _read(self, path: Path, *, expected_key: str) -> str | None:
        if not path.exists():
            return None
        try:
            raw: Any = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("cache payload must be an object")
            value = cast(dict[str, Any], raw)
            if value.get("key") != expected_key:
                raise ValueError("cache key mismatch")
            text = value.get("value")
            checksum = value.get("checksum")
            if not isinstance(text, str) or not isinstance(checksum, str):
                raise ValueError("cache fields have invalid types")
            if hashlib.sha256(text.encode()).hexdigest() != checksum:
                raise ValueError("cache checksum mismatch")
            return text
        except (OSError, ValueError, json.JSONDecodeError):
            self.stats.corruptions += 1
            path.replace(path.with_suffix(".corrupt"))
            return None

    def _write(self, path: Path, *, key_digest: str, value: str) -> None:
        payload = {
            "key": key_digest,
            "value": value,
            "checksum": hashlib.sha256(value.encode()).hexdigest(),
        }
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            text=True,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            temporary_path.replace(path)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
