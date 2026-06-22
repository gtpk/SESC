from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, cast

from pydantic import TypeAdapter

from ism.inference.runner_models import PredictionRecord

_RECORDS = TypeAdapter(tuple[PredictionRecord, ...])


class AtomicPredictionStore:
    def __init__(
        self,
        path: Path,
        *,
        before_replace: Callable[[Path], None] | None = None,
    ) -> None:
        self.path = path
        self.before_replace = before_replace

    def load(self) -> tuple[PredictionRecord, ...]:
        if not self.path.exists():
            return ()
        payloads: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"{self.path}:{line_number}: invalid prediction JSON"
                    ) from error
                if not isinstance(value, dict):
                    raise ValueError(f"{self.path}:{line_number}: prediction must be an object")
                payloads.append(cast(dict[str, Any], value))
        records = _RECORDS.validate_python(payloads)
        keys = [record.key for record in records]
        if len(keys) != len(set(keys)):
            raise ValueError(f"{self.path}: duplicate prediction keys")
        return records

    def append(self, records: Iterable[PredictionRecord]) -> None:
        existing = self.load()
        additions = tuple(records)
        existing_keys = {record.key for record in existing}
        addition_keys = [record.key for record in additions]
        if len(addition_keys) != len(set(addition_keys)):
            raise ValueError("new predictions contain duplicate keys")
        overlap = existing_keys & set(addition_keys)
        if overlap:
            raise ValueError(f"prediction keys already exist: {sorted(overlap)}")
        self._write((*existing, *additions))

    def _write(self, records: tuple[PredictionRecord, ...]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            text=True,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                for record in records:
                    stream.write(
                        json.dumps(
                            record.model_dump(mode="json"),
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                    )
                    stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            if self.before_replace is not None:
                self.before_replace(temporary_path)
            temporary_path.replace(self.path)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
