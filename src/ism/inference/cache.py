from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CompressionCacheKey:
    document_text: str
    method: str
    budget: int
    prompt_version: str
    model_id: str
    model_revision: str
    tokenizer_revision: str
    decoding_config: tuple[tuple[str, str], ...]

    def digest(self) -> str:
        payload = json.dumps(
            asdict(self),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()
