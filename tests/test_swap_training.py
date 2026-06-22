from __future__ import annotations

import json
from pathlib import Path

import pytest

from ism.training.swap import (
    LabelFamilies,
    LoRAConfig,
    SwapCheckpointStore,
    TinySwapTrainer,
    build_swap_matrix,
)


def families() -> LabelFamilies:
    return LabelFamilies(
        train=("Z1", "Z2"),
        dev=("D1", "D2"),
        test=("Q1", "Q2"),
    )


def test_p7_con_001_label_families_are_disjoint() -> None:
    families().validate()

    with pytest.raises(ValueError, match="overlap"):
        LabelFamilies(
            train=("Z1",),
            dev=("Z1",),
            test=("Q1",),
        ).validate()


def test_p7_con_002_raw_text_leakage_audit() -> None:
    value = families()

    assert value.audit_texts(split="train", texts=("Z1 Z2",)) == ()
    assert value.audit_texts(split="train", texts=("Z1 Q2",)) == ("Q2",)


def test_p7_cfg_001_lora_manifest_fields_are_complete() -> None:
    config = LoRAConfig(
        base_model="Qwen/Qwen2.5-7B-Instruct",
        base_revision="revision-a",
        tokenizer_revision="revision-a",
        rank=8,
        alpha=16,
        dropout=0.05,
        seed=42,
    )

    config.validate()
    with pytest.raises(ValueError, match="rank"):
        LoRAConfig(
            base_model="model",
            base_revision="revision",
            tokenizer_revision="revision",
            rank=0,
            alpha=16,
            dropout=0,
            seed=42,
        ).validate()


def test_p7_res_001_checkpoint_resume_restores_all_state(tmp_path: Path) -> None:
    trainer = TinySwapTrainer(base_revision="revision-a")
    store = SwapCheckpointStore(tmp_path / "checkpoint.json")
    first = trainer.train(steps=4)
    store.save(first)

    restored = store.load(expected_base_revision="revision-a")
    resumed = trainer.train(steps=3, state=restored)
    direct = trainer.train(steps=7)

    assert restored == first
    assert resumed.global_step == 7
    assert resumed == direct


def test_p7_res_002_checkpoint_revision_mismatch_is_rejected(tmp_path: Path) -> None:
    store = SwapCheckpointStore(tmp_path / "checkpoint.json")
    store.save(TinySwapTrainer(base_revision="revision-a").train(steps=1))

    with pytest.raises(ValueError, match="does not match"):
        store.load(expected_base_revision="revision-b")


def test_p7_io_001_checkpoint_is_complete_json(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    state = TinySwapTrainer(base_revision="revision-a").train(steps=2)

    SwapCheckpointStore(path).save(state)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["global_step"] == 2
    assert not list(tmp_path.glob("*.tmp"))


def test_p7_int_001_tiny_training_reduces_loss_and_round_trips(tmp_path: Path) -> None:
    trainer = TinySwapTrainer(base_revision="revision-a")
    initial = trainer.initial_state()
    trained = trainer.train(steps=5)
    store = SwapCheckpointStore(tmp_path / "adapter.json")
    store.save(trained)

    loaded = store.load(expected_base_revision="revision-a")

    assert trained.loss < initial.loss
    assert loaded == trained


def test_p7_int_002_swap_matrix_has_four_aligned_conditions() -> None:
    matrix = build_swap_matrix(("q1", "q2", "q3"))

    assert len(matrix) == 12
    assert all(
        len({question_id for question_id, item_condition in matrix if item_condition == condition})
        == 3
        for condition in {condition for _, condition in matrix}
    )


def test_p7_env_001_eval_only_checkpoint_load_needs_no_trainer(tmp_path: Path) -> None:
    store = SwapCheckpointStore(tmp_path / "adapter.json")
    state = TinySwapTrainer(base_revision="revision-a").train(steps=2)
    store.save(state)

    loaded = SwapCheckpointStore(tmp_path / "adapter.json").load(
        expected_base_revision="revision-a"
    )

    assert loaded.parameter == state.parameter
