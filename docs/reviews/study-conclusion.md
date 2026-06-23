# Study conclusion — mixed-results wrap-up

- 날짜: 2026-06-23
- 결정: prompt-only ISM 연구를 **정직한 mixed-results 논문**으로 마무리한다. 더 이상 방향 전환 없음.

## 무엇이 입증됐나 / 안 됐나

| 항목 | 결과 | 근거 |
|---|---|---|
| RQ1 — ISM 내부 구조가 사용되는가 | **예 (dev-scale)** | 6.1 N=240: Δsymbol +0.108 (p=5e-4), Δmap_flip +0.079 (p=0.032), derange n.s. |
| RQ3 — 동일 예산에서 ISM이 요약보다 효율적인가 | **아니오** | 6.3 N=40: paired summary−ISM +0.25~+0.375, McNemar p<0.01 (모든 예산) |
| RQ4 — 재사용에서 ISM이 유리한가 | **아니오** | 6.4: 캐시는 모두 n=2에서 full 추월하나 frontier에서 summary가 ISM 지배 |
| 초기 Δmap≈0 | **측정 결함이었음** | 압축 purity 부족 + 내용 보존적 derangement → 교정 후 RQ1 신호 출현 |

## 핵심 메시지

prompt-only ISM은 "LLM이 만들고 LLM이 다시 읽는 텍스트"라 자연어 요약과 같은 범주이며, 그 범주에서
요약이 더 짧고 정확하다. **부록 A 기준 #1(ISM > Summary) 실패.** ISM의 잠재 가치는 효율이 아니라
parser/checker/executor가 다루는 **실행 가능한 semantic IR**에 있으며, 이는 후속 과제(부록 B).

## 마무리 작업 (논문 반영 완료)

1. 제목/부제 → mixed-results ("…: A Mixed-Results Study")
2. 초록·서론 → 효율 기대 낮춤 + 결과 미리보기(혼합)
3. §8 결과 도입 → mixed-results 요약
4. §9.3.1/§9.5 → 요약 우세·filler artifact·효율 아닌 inspectability
5. §11 결론 → 한계 규명 + semantic IR 방향
6. 부록 A.2 → 기준 #1 실패 명시
7. 재현성 진술 → docs/evidence 위치·해시
8. 부록 B → 실행 가능한 semantic IR 후속 설계(compile-and-execute, programmatic editability)

## 코드 상태 (durable)

전 실험 파이프라인 구현·푸시·그린(206 tests): 6.1 ablation(+강한 corruption), 6.3 fixed-budget
(+paired contrast, merge), 6.4 reuse, 진단 도구(compress-audit, diagnostics), long-context generator,
샤딩/merge. 미실행: 6.2 Swap(LoRA), QASPER end-to-end, full registered scale.
