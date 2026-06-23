# Inspectable Symbolic Compression (ISM)

A study of **Inspectable Symbolic Compression** for long-context LLM reasoning:
compressing a long document into reusable discrete text symbols (`Z1`, `Z2`, …)
plus a short dictionary, instead of selecting source tokens or compressing into
continuous vectors. Because the representation is ordinary tokens with an explicit
symbol→meaning map, you can remove the dictionary, corrupt its mappings, or swap
labels and measure the effect on downstream reasoning.

This repository contains the full experiment framework (`src/ism/`, CLI `ism`),
the reproducible run evidence (`docs/evidence/`), and the paper.

## Paper

**Inspectable Symbolic Compression for Long-Context Reasoning: A Mixed-Results
Study Against Natural-Language Summaries** — Taehyuk Kwon (NeurIPS 2026 format).

- 📄 **[View on GitHub](paper/ism-mixed-results.pdf)** ·
  **[Download PDF](https://github.com/gtpk/SESC/raw/main/paper/ism-mixed-results.pdf)**
- LaTeX source: [paper/ism-mixed-results.tex](paper/ism-mixed-results.tex)
  (compile with `tectonic paper/ism-mixed-results.tex`)

### Findings (honest, mixed results)

| RQ | Question | Result |
|---|---|---|
| RQ1 | Is ISM's internal structure actually used by the reasoner? | **Yes** (dev scale): inverting dictionary conclusions and removing symbolic structure each significantly lower accuracy; permuting arbitrary labels does not. |
| RQ3 | At a matched token budget, is ISM more efficient than a same-model summary? | **No**: a natural-language summary is both more accurate and cheaper (McNemar *p* < 0.01 at every budget). |
| RQ4 | Does ISM win on the reuse cost–accuracy frontier? | **No**: the summary dominates ISM on both cost and accuracy. |

We do **not** claim ISM as a better compressor. The contribution is to delimit
where prompt-only symbolic compression fails, and to argue its remaining promise
is as a *programmatically executable semantic IR* handled by a
parser/checker/executor outside the LLM (paper Appendix B). Reproducible run
evidence (artifacts, hashes, environment, commands) is under
[docs/evidence/](docs/evidence/README.md).

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

- [Paper (PDF)](paper/ism-mixed-results.pdf) · [LaTeX source](paper/ism-mixed-results.tex)
- [Research draft](deep-research-report.md)
- [Implementation and validation plan](ism-system-plan.md)
- [Phase completion reports](docs/README.md)
