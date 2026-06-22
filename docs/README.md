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
| 9 | Main run, 통계, 보고 | 대기 | - |

## 문서 구분

- `deep-research-report.md`: 논문 주장과 실험 설계
- `ism-system-plan.md`: 구현 계획, TC, 품질·비용 게이트
- `docs/phases/`: 각 Phase에서 실제로 구현하고 검증한 내용

계획과 완료 기록이 충돌하면 완료 보고서의 실행 증거를 사실 기록으로 보고, 계획 문서는 다음
작업을 위해 갱신한다.
