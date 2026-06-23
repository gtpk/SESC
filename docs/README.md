# ISM 개발 문서

이 디렉터리는 구현 단계별 완료 증거와 운영 결정을 기록한다.

## Phase 상태

| Phase | 범위 | 상태 | 완료 보고서 |
|---|---|---|---|
| 0 | 프로젝트 골격, 설정, CLI, 로깅, 비용 dry-run | 완료 | [Phase 0](phases/phase-0-foundation.md) |
| 1 | Synthetic rule graph와 executor | 완료 | [Phase 1](phases/phase-1-synthetic-engine.md) |
| 2 | ISM 표현, parser, intervention | 완료 | [Phase 2](phases/phase-2-representation.md) |
| 3 | Inference pipeline과 resume/cache | 완료 | [Phase 3](phases/phase-3-inference.md) |
| 4 | Ablation orchestration | 완료 | [Phase 4](phases/phase-4-conditions.md) |
| 5 | Fixed-Budget orchestration | 완료 | [Phase 5](phases/phase-5-budgets.md) |
| 6 | Reuse와 cache 비용 계산 | 완료 | [Phase 6](phases/phase-6-cache-cost.md) |
| 7 | Swap LoRA local contract | 완료 | [Phase 7](phases/phase-7-swap-training.md) |
| 8 | QASPER adapter | 완료 | [Phase 8](phases/phase-8-qasper.md) |
| 9 | 통계·보고·서버 진입 | 로컬 완료, Colab S0 차단 | [Phase 9](phases/phase-9-local-validation.md) |
| 3b | Transformers GPU backend (`ism run`, S1 준비) | 로컬 완료, Colab S1 대기(GPU 런타임 필요) | [Phase 3b](phases/phase-3b-transformers-backend.md) |

## 결정·리뷰·증거

- `docs/decisions/`: 설계 결정 기록 (ADR)
  - [ADR 0001 — config_hash 배포 독립성](decisions/0001-config-hash-is-deployment-independent.md)
  - [ADR 0002 — QASPER 채점 규약](decisions/0002-qasper-scoring.md)
- `docs/reviews/`: 검토 메모
  - [논문 실험 갭 분석](reviews/paper-experiment-gaps.md)
  - [LLM ISM 진단 (Δmap≈0 원인)](reviews/llm-ism-diagnostic.md)
  - [연구 마무리 — mixed-results](reviews/study-conclusion.md)
- `docs/evidence/`: 재현 가능한 실행 증거 (산출물·체크섬·환경)
  - [증거 인덱스 (S0/S1)](evidence/README.md)

## 문서 구분

- `deep-research-report.md`: 논문 주장과 실험 설계
- `ism-system-plan.md`: 구현 계획, TC, 품질·비용 게이트
- `docs/phases/`: 각 Phase에서 실제로 구현하고 검증한 내용

계획과 완료 기록이 충돌하면 완료 보고서의 실행 증거를 사실 기록으로 보고, 계획 문서는 다음
작업을 위해 갱신한다.
