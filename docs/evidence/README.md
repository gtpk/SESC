# Evidence

실행 증거를 단계별로 보관한다. 각 항목은 산출물 원본 + 체크섬 + 환경 + 재현 절차를 포함한다.

| 단계 | 내용 | 상태 | 증거 |
|---|---|---|---|
| S0 | Colab 연결·환경·config parity | PASS | 아래 표 |
| S1 | GPU 모델 로드 + 1 batch (Qwen2.5-7B 4-bit) | PASS (acc 0.70) | [s1-qwen7b/](s1-qwen7b/README.md) |
| 6.1 (LLM 압축기, 메인) | Dictionary Ablation dev pilot, N=36 | 예비 (Δmap≈0, Δsymbol n.s.) | [ablation-qwen7b-llm-dev/](ablation-qwen7b-llm-dev/README.md) |
| 6.1 (gold-oracle, 강건성) | Dictionary Ablation dev pilot, N=40 | 예비 (Δmap=0, Δsymbol≈0) | [ablation-qwen7b-dev/](ablation-qwen7b-dev/README.md) |
| 진단 v1 | compress-audit (LLM ISM 구조) | purity 0.70 / self-cont 0.71 | [compress-audit-qwen7b-dev/](compress-audit-qwen7b-dev/README.md) |
| 진단 v2 | compress-audit (결론 강제 압축기, 71205fe) | purity 1.0 / self-cont 1.0, 단 실패 6/20(empty_relations) | [compress-audit-qwen7b-v2/](compress-audit-qwen7b-v2/README.md) |
| 진단 v3 | compress-audit (생성 budget 512, 6087f03) | purity 1.0 / self-cont 1.0 / rel-struct 0.96 / 실패 0/20 | [compress-audit-qwen7b-v3/](compress-audit-qwen7b-v3/README.md) |

## S0 — config parity (COL-ENV-004)

로컬과 Colab에서 같은 config가 동일한 `config_hash`를 산출함을 확인.

| config | local config_hash | Colab config_hash | 결과 |
|---|---|---|---|
| `configs/experiments/smoke.yaml` | `92701d9ee4b8825f5fc4e7a740e9840020bc2c0488821d7bafdd37150d553deb` | 동일 | PASS |
| `configs/experiments/s1_qwen7b.yaml` | `fe0c0667cfd3df2198f65add086cdbe13e20edd475f8a205f799277ea56c1bb7` | 동일 | PASS |

재현:
```bash
uv run ism dry-run --config configs/experiments/smoke.yaml      # -> 92701d9e...
uv run ism dry-run --config configs/experiments/s1_qwen7b.yaml  # -> fe0c0667...
```
config_hash가 배포 경로와 무관하게 일치하는 근거는 [ADR 0001](../decisions/0001-config-hash-is-deployment-independent.md).
