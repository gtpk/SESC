# Evidence — 6.4 Reuse cost/accuracy tradeoff (RQ4, analytic)

문서당 1회 압축 표현을 n개 질문에 재사용할 때의 토큰 비용·정확도 tradeoff. **분석적**(GPU 없음):
토큰 수(|x|,|q|)는 long-context 데이터, |z|·정확도는 6.3 N=40 fixed-budget summary(budget 256)에서.

| 항목 | 값 |
|---|---|
| commit | `5dffe04` · 입력: [fixed-budget-N40](../fixed-budget-N40/README.md) (budget 256) |
| \|x\| (full doc) | 1348 tok | \|q\| (question) | 5.5 tok |
| \|z\| | model_summary 86 · ism 97 · oracle 88 · keyword 233 |
| 정확도 | full 0.700 · summary 0.787 · ism 0.475 · oracle 0.512 · keyword 0.512 |
| reuse_summary.json sha256 | `0645b65c0987d36fe498571567c35872b0d14705f69fc3ede5ae1adbd8fe053b` (Colab) |

## 비용 (end-to-end 토큰, paper §6.4 공식)

| method | n=1 | n=8 | n=32 | n=64 | acc |
|---|---:|---:|---:|---:|---:|
| Full Context | 1354 | 10828 | 43312 | 86624 | 0.700 |
| Model Summary | 1526 | 2168 | 4369 | **7305** | **0.787** |
| ISM | 1548 | 2265 | 4725 | 8005 | 0.475 |
| Oracle Gold | 1530 | 2184 | 4428 | 7420 | 0.512 |
| Keyword | 1820 | 3492 | 9225 | 16868 | 0.512 |

**Crossover(캐시 end-to-end < full_context): 모든 방법 n=2.** serving-only는 일회성 압축 비용을
제외해 더 낮다(예: summary n=64 serving 5870).

## 해석

- **재사용은 압축의 분명한 실용 이점**: 질문 2개부터 모든 압축 방법이 full_context보다 싸고,
  n=64에서 ~12배 저렴(86624 → 7305). 이는 ISM/summary 공통 이점이다(ISM만의 것이 아님).
- **캐시 방법 간에는 Model Summary가 비용·정확도 frontier를 지배**한다: summary는 ISM보다
  토큰이 적고(86 vs 97) 정확도가 높다(0.787 vs 0.475). 즉 reuse에서도 ISM은 summary에
  **dominated**된다.
- 정직한 정리(논문 §9):
  - **Model Summary = 더 효율적인 reusable *text* cache**
  - **ISM = 덜 효율적이지만 *검사·개입 가능한* reusable *semantic* cache**
  → ISM의 생존 논리는 효율이 아니라 **intervention/inspection**이며, 이를 직접 입증하는
    constructive intervention 실험이 다음 핵심이다.

## 한계
질문당 정확도는 n과 무관(같은 캐시가 모든 질문에 답)하므로 정확도는 method-level 상수다. 비용은
분석적 모델이며 KV-cache/지연/배치 효과는 §10대로 별도다. dev pilot 토큰 수 기반.

## 재현
```bash
python -m ism run-reuse --config configs/experiments/fixed_budget_qwen7b_long.yaml \
  --output artifacts/runs/reuse \
  --fixed-budget-summary artifacts/runs/fb_pilot/merged/fixed_budget_summary.json \
  --budget 256 --ns 1 2 4 8 16 32 64
```
