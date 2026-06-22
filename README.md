# ISM Research

Implementation workspace for the Inspectable Symbolic Compression experiments.

## Local setup

```bash
uv sync --dev
uv run ism validate-config --config configs/experiments/smoke.yaml
uv run ism dry-run --config configs/experiments/smoke.yaml
uv run pytest
```

The local repository is the source of truth. Colab is used only after local blocking tests pass.

## GPU inference (Colab, S1+)

The real-model backend (`backend: transformers`) is an optional extra so local
mock/CPU runs and the test suite never pull in torch:

```bash
# In a GPU environment (e.g. Colab). torch ships with Colab; do not reinstall it.
pip install -e ".[gpu]"
ism validate-config --config configs/experiments/s1_qwen7b.yaml
ism run --config configs/experiments/s1_qwen7b.yaml --output artifacts/runs/s1
```

`ism run` selects the backend from `model.backend` via
[`build_text_generator`](src/ism/inference/factory.py); the GPU adapter lives in
[transformers_backend.py](src/ism/inference/transformers_backend.py) and imports
torch/transformers lazily. `config_hash` is deployment-independent so local and
Colab agree (see [ADR 0001](docs/decisions/0001-config-hash-is-deployment-independent.md)).

## Documentation

- [Research draft](deep-research-report.md)
- [Implementation and validation plan](ism-system-plan.md)
- [Phase completion reports](docs/README.md)
