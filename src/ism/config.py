from __future__ import annotations

import hashlib
import json
import os
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Split(StrEnum):
    TRAIN = "train"
    DEV = "dev"
    TEST = "test"


class ExecutionStage(StrEnum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    S0 = "S0"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"


class ExperimentConfig(StrictModel):
    name: Annotated[str, Field(min_length=1)]
    seed: int = 42
    split: Split = Split.DEV
    tuning_mode: bool = False

    @model_validator(mode="after")
    def reject_test_tuning(self) -> ExperimentConfig:
        if self.split is Split.TEST and self.tuning_mode:
            raise ValueError("experiment.tuning_mode cannot be true when split is test")
        return self


class DatasetConfig(StrictModel):
    name: Literal["synthetic", "qasper"]
    path: Path
    max_documents: Annotated[int, Field(gt=0)]
    questions_per_document: Annotated[int, Field(gt=0)] = 1
    # Long-context profile: when set, synthetic documents are padded with
    # deterministic neutral filler to this whitespace-token range (graph,
    # questions, and answers are unchanged). Needed for meaningful fixed-budget
    # compression (paper §5.1: 700-2000 tokens).
    document_min_tokens: Annotated[int, Field(gt=0)] | None = None
    document_max_tokens: Annotated[int, Field(gt=0)] | None = None

    @model_validator(mode="after")
    def validate_document_length(self) -> DatasetConfig:
        if (self.document_min_tokens is None) != (self.document_max_tokens is None):
            raise ValueError("document_min_tokens and document_max_tokens must be set together")
        if (
            self.document_min_tokens is not None
            and self.document_max_tokens is not None
            and self.document_min_tokens > self.document_max_tokens
        ):
            raise ValueError("document_min_tokens must not exceed document_max_tokens")
        return self


class RuntimeConfig(StrictModel):
    device: Literal["cpu", "cuda", "mps"] = "cpu"


class ModelConfig(StrictModel):
    compressor: Annotated[str, Field(min_length=1)]
    reasoner: Annotated[str, Field(min_length=1)]
    backend: Literal["mock", "transformers"] = "mock"
    model_revision: Annotated[str, Field(min_length=1)]
    tokenizer_revision: Annotated[str, Field(min_length=1)]
    load_in_4bit: bool = False
    temperature: Annotated[float, Field(ge=0)] = 0.0


class CompressionConfig(StrictModel):
    budget: Annotated[int, Field(gt=0)]
    prompt_version: Annotated[str, Field(min_length=1)]
    max_regeneration_attempts: Annotated[int, Field(ge=1)]
    max_new_tokens: Annotated[int, Field(ge=1)]
    # Decoding budget the compressor may use to emit a complete
    # [DICTIONARY]/[RELATIONS] block. Separate from `budget`, which still bounds
    # the *final* representation length. Larger output is regenerated/rejected by
    # the budget check, so this only gives the model working room.
    generation_max_new_tokens: Annotated[int, Field(ge=1)] = 512


class OutputConfig(StrictModel):
    artifact_dir: Path
    save_raw_generations: bool = True
    checkpoint_every: Annotated[int, Field(ge=1)] = 10


class ExecutionBudgetConfig(StrictModel):
    stage: ExecutionStage
    max_documents: Annotated[int, Field(gt=0)]
    max_questions_per_document: Annotated[int, Field(gt=0)]
    max_conditions: Annotated[int, Field(gt=0)]
    max_budgets: Annotated[int, Field(gt=0)] = 1
    max_seeds: Annotated[int, Field(gt=0)] = 1
    max_generation_attempts: Annotated[int, Field(ge=1)]
    max_new_tokens: Annotated[int, Field(ge=1)]
    max_gpu_hours: Annotated[float, Field(ge=0)]
    stop_on_error_rate: Annotated[float, Field(ge=0, le=1)]
    stop_on_parse_failure_rate: Annotated[float, Field(ge=0, le=1)]


Condition = Literal[
    "full_context",
    "full_symbol_dict",
    "symbol_only",
    "corrupted_dict",
    "flipped_dict",
    "blank_dict",
    "random_symbol",
    "model_summary",
    "keyword_extract",
    "llmlingua_2",
    "unseen_swap_dict",
    "unseen_swap_no_dict",
]


class AppConfig(StrictModel):
    experiment: ExperimentConfig
    dataset: DatasetConfig
    runtime: RuntimeConfig
    model: ModelConfig
    compression: CompressionConfig
    conditions: Annotated[list[Condition], Field(min_length=1)]
    output: OutputConfig
    execution_budget: ExecutionBudgetConfig

    # Deployment root used to resolve the path fields below. Excluded from the
    # serialized identity so config_hash stays independent of where the repo
    # lives (e.g. local vs Colab). See stable_json().
    _project_root: Path | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def validate_consistency(self) -> AppConfig:
        if len(self.conditions) != len(set(self.conditions)):
            raise ValueError("conditions must not contain duplicates")
        if self.runtime.device == "cpu" and self.model.load_in_4bit:
            raise ValueError("model.load_in_4bit cannot be true when runtime.device is cpu")
        if self.model.backend == "mock" and self.runtime.device != "cpu":
            raise ValueError("mock backend requires runtime.device=cpu")
        if self.execution_budget.max_documents < self.dataset.max_documents:
            raise ValueError("execution_budget.max_documents must cover dataset.max_documents")
        if self.execution_budget.max_questions_per_document < self.dataset.questions_per_document:
            raise ValueError(
                "execution_budget.max_questions_per_document must cover "
                "dataset.questions_per_document"
            )
        if self.execution_budget.max_conditions < len(self.conditions):
            raise ValueError("execution_budget.max_conditions must cover configured conditions")
        if (
            self.execution_budget.max_generation_attempts
            != self.compression.max_regeneration_attempts
        ):
            raise ValueError(
                "execution_budget.max_generation_attempts must equal "
                "compression.max_regeneration_attempts"
            )
        if self.execution_budget.max_new_tokens != self.compression.max_new_tokens:
            raise ValueError(
                "execution_budget.max_new_tokens must equal compression.max_new_tokens"
            )
        if self.execution_budget.stage.value.startswith("L"):
            if self.execution_budget.max_gpu_hours != 0:
                raise ValueError("local stages must set execution_budget.max_gpu_hours to 0")
        elif self.execution_budget.max_gpu_hours <= 0:
            raise ValueError("server stages require execution_budget.max_gpu_hours > 0")
        return self

    def resolved(self, project_root: Path) -> AppConfig:
        root = project_root.resolve()
        dataset_path = _resolve_path(self.dataset.path, root)
        artifact_dir = _resolve_path(self.output.artifact_dir, root)
        new = self.model_copy(
            update={
                "dataset": self.dataset.model_copy(update={"path": dataset_path}),
                "output": self.output.model_copy(update={"artifact_dir": artifact_dir}),
            }
        )
        object.__setattr__(new, "_project_root", root)
        return new

    def stable_json(self) -> str:
        data = self.model_dump(mode="json")
        # The path fields are resolved to absolute, deployment-specific paths at
        # load time. Relativize them against the project root (as POSIX) so the
        # serialized identity — and therefore config_hash — is identical across
        # machines (local <-> Colab). See COL-ENV-004.
        root = self._project_root
        if root is not None:
            data["dataset"]["path"] = _identity_path(self.dataset.path, root)
            data["output"]["artifact_dir"] = _identity_path(self.output.artifact_dir, root)
        return (
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

    def config_hash(self) -> str:
        return hashlib.sha256(self.stable_json().encode("utf-8")).hexdigest()


def discover_project_root(start: Path) -> Path:
    candidate = start.resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for directory in (candidate, *candidate.parents):
        if (directory / "pyproject.toml").is_file():
            return directory
    raise FileNotFoundError(f"could not find pyproject.toml from {start}")


def load_config(path: Path, *, project_root: Path | None = None) -> AppConfig:
    config_path = path.resolve()
    root = project_root.resolve() if project_root else discover_project_root(config_path)
    with config_path.open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise ValueError("config root must be a mapping")
    return AppConfig.model_validate(raw).resolved(root)


def _resolve_path(path: Path, project_root: Path) -> Path:
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def _identity_path(resolved_path: Path, project_root: Path) -> str:
    """Render a resolved path as a stable, machine-independent identity string.

    Paths under the project root become POSIX relative paths (e.g.
    "data/processed/synthetic-v1"); paths outside it fall back to their POSIX
    absolute form. The result never contains the deployment-specific root.
    """
    relative = os.path.relpath(resolved_path, project_root)
    if relative.startswith(".."):
        return resolved_path.as_posix()
    return Path(relative).as_posix()
