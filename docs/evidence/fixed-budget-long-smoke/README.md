# Evidence — 6.3 Fixed-Budget Comparison (long-context smoke)

RQ3 첫 실측. **N=10 문서 smoke**(통계 아님): budget fairness·실행경로·frontier 형태 검증 + 방향성 신호.

| 항목 | 값 |
|---|---|
| config | [configs/experiments/fixed_budget_qwen7b_long.yaml](../../../configs/experiments/fixed_budget_qwen7b_long.yaml) (700–2000 tok) |
| commit | `714eff1` · Tesla T4 · 2757s |
| 규모 | 10 docs × 2q × (full + 4 methods × 4 budgets) = 320 predictions, 0 errors |
| full_context 평균 토큰 | **1262** (예산 64–512가 진짜 압축) |
| budget fairness | over-budget **0** / 셀 실패 0 (ism@64 제외, floor) |

## 결과 (AR = vs full_context, N=20 문항)

| method | b64 | b128 | b256 | b512 |
|---|---|---|---|---|
| ism (AR / ES) | (floor 실패) | 0.86 / 11.2 | 0.86 / 11.0 | 0.86 / 10.8 |
| model_summary | 1.29 / 76.9 | 1.21 / 63.3 | **1.36 / 19.9** | 1.21 / 13.3 |
| keyword_extract | 0.86 / 16.9 | 0.79 / 7.7 | 0.79 / 4.3 | 0.86 / 4.1 |
| oracle_gold_summary | 0.86 / 18.3 | 0.86 / 12.3 | 0.86 / 12.3 | 0.86 / 12.3 |

full_context: Acc 0.70, AR 1.0, CR 1.0.

## 해석 (예비, N=10)

- **model_summary가 ISM을 AR·ES 모두에서 압도**. 요약은 full_context(AR>1)보다도 높은데,
  1262토큰 중 대부분이 중립 filler 노이즈라 요약이 답 관련 규칙만 추려 오히려 유리한 것으로
  보인다(노이즈 제거 효과).
- ISM AR 0.86, ES ~11 — keyword/oracle와 비슷한 수준, summary보다 낮음.
- keyword CR이 예산 따라 단조 증가(0.05→0.10→0.18→0.21) — 짧은 문서에서의 포화 해소.
- ism@64는 floor(~100토큰)로 미생성 — stress point로 남기고 primary는 128+.

→ **부록 A 기준 #1("ISM > Model Summary in AR or ES")은 이 smoke에서 충족되지 않을 가능성**이
크다. 논문 §9.3이 예견한 경우로, ISM의 차별점을 "토큰 효율"이 아니라 "검사·개입 가능성"
(6.1에서 입증)으로 재정의하는 해석을 지지한다. N=10이라 통계 결론은 보류.

## 한계
N=10 단일 seed. model_summary AR>1은 filler 노이즈의 부작용일 수 있어 filler 설계(노이즈 강도)
재검토가 필요. pilot(40 docs)에는 fixed-budget 샤딩/merge가 필요(현재 미구현).

## 재현
```bash
python -m ism run-fixed-budget --config configs/experiments/fixed_budget_qwen7b_long.yaml \
  --output artifacts/runs/fixed_budget_long_smoke --doc-count 10 \
  --budgets 64 128 256 512 \
  --methods full_context ism model_summary keyword_extract oracle_gold_summary
```
