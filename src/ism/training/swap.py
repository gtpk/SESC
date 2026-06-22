from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class LabelFamilies:
    train: tuple[str, ...]
    dev: tuple[str, ...]
    test: tuple[str, ...]

    def validate(self) -> None:
        families = {
            "train": set(self.train),
            "dev": set(self.dev),
            "test": set(self.test),
        }
        if any(len(values) == 0 for values in families.values()):
            raise ValueError("label families must not be empty")
        if any(len(values) != len(getattr(self, name)) for name, values in families.items()):
            raise ValueError("labels must be unique within each family")
        overlaps = (
            families["train"] & families["dev"]
            | families["train"] & families["test"]
            | families["dev"] & families["test"]
        )
        if overlaps:
            raise ValueError(f"label families overlap: {sorted(overlaps)}")

    def audit_texts(self, *, split: str, texts: tuple[str, ...]) -> tuple[str, ...]:
        self.validate()
        protected = {
            "train": (*self.dev, *self.test),
            "dev": (*self.train, *self.test),
            "test": (*self.train, *self.dev),
        }.get(split)
        if protected is None:
            raise ValueError(f"unknown split: {split}")
        return tuple(label for label in protected if any(label in text for text in texts))


@dataclass(frozen=True)
class LoRAConfig:
    base_model: str
    base_revision: str
    tokenizer_revision: str
    rank: int
    alpha: int
    dropout: float
    seed: int

    def validate(self) -> None:
        if not self.base_model or not self.base_revision or not self.tokenizer_revision:
            raise ValueError("model and revision fields must not be empty")
        if self.rank < 1 or self.alpha < 1:
            raise ValueError("LoRA rank and alpha must be positive")
        if not 0 <= self.dropout < 1:
            raise ValueError("LoRA dropout must be in [0, 1)")


@dataclass(frozen=True)
class SwapTrainerState:
    base_revision: str
    global_step: int
    parameter: float
    optimizer_momentum: float
    scheduler_scale: float
    loss: float


class SwapCheckpointStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, state: SwapTrainerState) -> None:
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
                json.dump(asdict(state), stream, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            temporary_path.replace(self.path)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise

    def load(self, *, expected_base_revision: str) -> SwapTrainerState:
        raw: Any = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("checkpoint must be an object")
        payload = cast(dict[str, Any], raw)
        state = SwapTrainerState(
            base_revision=str(payload["base_revision"]),
            global_step=int(payload["global_step"]),
            parameter=float(payload["parameter"]),
            optimizer_momentum=float(payload["optimizer_momentum"]),
            scheduler_scale=float(payload["scheduler_scale"]),
            loss=float(payload["loss"]),
        )
        if state.base_revision != expected_base_revision:
            raise ValueError(
                f"checkpoint base revision {state.base_revision} does not match "
                f"{expected_base_revision}"
            )
        return state


class TinySwapTrainer:
    def __init__(self, *, base_revision: str, learning_rate: float = 0.1) -> None:
        self.base_revision = base_revision
        self.learning_rate = learning_rate

    def initial_state(self) -> SwapTrainerState:
        return SwapTrainerState(
            base_revision=self.base_revision,
            global_step=0,
            parameter=0,
            optimizer_momentum=0,
            scheduler_scale=1,
            loss=1,
        )

    def train(
        self,
        *,
        steps: int,
        state: SwapTrainerState | None = None,
    ) -> SwapTrainerState:
        if steps < 1:
            raise ValueError("steps must be positive")
        current = state or self.initial_state()
        if current.base_revision != self.base_revision:
            raise ValueError("trainer and state base revisions do not match")
        parameter = current.parameter
        momentum = current.optimizer_momentum
        scheduler = current.scheduler_scale
        for _ in range(steps):
            gradient = 2 * (parameter - 1)
            momentum = 0.9 * momentum + gradient
            parameter -= self.learning_rate * scheduler * momentum
            scheduler *= 0.99
        loss = (parameter - 1) ** 2
        return SwapTrainerState(
            base_revision=self.base_revision,
            global_step=current.global_step + steps,
            parameter=parameter,
            optimizer_momentum=momentum,
            scheduler_scale=scheduler,
            loss=loss,
        )


def build_swap_matrix(question_ids: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    conditions = (
        "seen_labels_with_dict",
        "seen_labels_without_dict",
        "unseen_labels_with_dict",
        "unseen_labels_without_dict",
    )
    return tuple(
        (question_id, condition) for question_id in question_ids for condition in conditions
    )
