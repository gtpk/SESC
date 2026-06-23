# Evidence — compress-audit v3 (generation budget 512, commit 6087f03)

truncation 수정(#1.5) 후 재측정. 모든 목표 달성.

| 지표 | v1 | v2 | **v3** |
|---|---:|---:|---:|
| rule_coverage | 0.70 | 1.00 | **1.00** |
| self_containment | 0.71 | 1.00 | **1.00** |
| relations_structure | 0.79 | 0.61 | **0.96** |
| compressed | 18/20 | 14/20 | **20/20** |
| failures | 2 | 6 | **0** |

ISM이 결론까지 담은 규칙 + 구조화된 relations를 갖춘 고품질 표현이 됨. 6.1 재실행 준비 완료.

**주의:** corruption_preserves_content는 여전히 **1.0** — derangement는 정의 집합을
보존하므로, ISM 품질이 좋아져도 Δmap은 여전히 ≈0일 수 있음(2차 원인, 다음 단계).

## 재현
```bash
# Colab GPU, commit 6087f03
python -m ism compress-audit --config configs/experiments/ablation_qwen7b.yaml --output artifacts/runs/compress_audit
```
