# Evidence — compress-audit (LLM ISM structure)

LLM 압축기가 만든 ISM의 구조 진단. 분석·결론은 [llm-ism-diagnostic.md](../../reviews/llm-ism-diagnostic.md).

| 항목 | 값 |
|---|---|
| config | [configs/experiments/ablation_qwen7b.yaml](../../../configs/experiments/ablation_qwen7b.yaml) |
| commit | `ebc4222` · GPU Tesla T4 · 소요 517s |
| compressed | 18/20 (2 실패), mean_attempts 1.06 |
| rule_coverage (purity) | **0.70** |
| self_containment | **0.71** (결론 누락 ~29%) |
| relations_structure | **0.79** |
| corruption_preserves_content | **1.00** |
| majority_baseline | 0.55 (both types) |

핵심: LLM이 **조건은 남기고 결론(risk=HIGH 등)을 버린다** → 사전에 정답 매핑이 자주 없음.
샘플은 [sample_isms.md](sample_isms.md).

## 파일
- `compression_audit.json` — 집계 지표
- `sample_isms.md` — doc0/doc1 ISM 원문
- `SHA256SUMS` — audit + compressions.jsonl(20줄, Colab 보관) sha256
- `environment.json`

## 재현
```bash
# Colab GPU, commit ebc4222
python -m ism compress-audit --config configs/experiments/ablation_qwen7b.yaml \
  --output artifacts/runs/compress_audit
```
