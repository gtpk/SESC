# Evidence — 6.3 Fixed-Budget pilot, N=40 (long-context, 4×10 shards)

RQ3 dev pilot. long-context 문서(700–2000 tok, full_context 평균 1326), 4×10 샤드 + resume + merge.
**primary = 같은 문항 paired summary vs ISM**(filler artifact와 분리됨). budget 64는 ISM floor라 제외.

| 항목 | 값 |
|---|---|
| config | [configs/experiments/fixed_budget_qwen7b_long.yaml](../../../configs/experiments/fixed_budget_qwen7b_long.yaml) |
| commit | `5d4500d` · Tesla T4 · 4 shards (~29min each; shard3 느림) + merge |
| 규모 | 40 docs × 2q × (full + 4 methods × 3 budgets) = 1040 predictions, 0 errors, N=80 문항/셀 |
| 셀 실패 | 0 (over-budget 0) |

## 셀 결과 (Acc / AR / ES)

| method | b128 | b256 | b512 |
|---|---|---|---|
| Full Context | 0.700 / 1.000 / 1.0 (CR 1.0, 1326 tok) | | |
| Model Summary | 0.725 / 1.036 / 51.3 | 0.788 / 1.125 / 17.3 | 0.838 / 1.196 / 13.3 |
| ISM | 0.475 / 0.679 / 9.4 | 0.475 / 0.679 / 9.3 | 0.463 / 0.661 / 8.9 |
| Keyword Extract | 0.500 / 0.714 / 7.4 | 0.513 / 0.732 / 4.2 | 0.525 / 0.750 / 3.6 |
| Oracle Gold Summary | 0.513 / 0.732 / 11.0 | 0.513 / 0.732 / 11.0 | 0.513 / 0.732 / 11.0 |

## Primary paired contrast — summary_vs_ism (same questions, N=80)

| budget | Δ = Acc(summary) − Acc(ism) | 95% CI | McNemar p | discordant (summary✓ism✗ / ism✓summary✗) |
|---:|---:|---:|---:|---|
| 128 | **+0.250** | [0.100, 0.400] | **0.0029** | 31 / 11 |
| 256 | **+0.3125** | [0.175, 0.450] | **1.1e-4** | 33 / 8 |
| 512 | **+0.375** | [0.250, 0.500] | **2.3e-7** | 33 / 3 |

## 해석

**model_summary가 ISM을 모든 예산에서 유의하게(McNemar p<0.01, 512에선 p<1e-6) 능가한다.** 이는
같은 문항 paired 비교이고 두 방법 모두 filler를 제거하므로, 앞선 filler artifact(AR vs full_context
오염)와 **독립적**이다. 격차는 예산이 커질수록 증가(+0.25→+0.31→+0.375). 부록 A 기준 #1
(ISM이 AR 또는 ES에서 Model Summary 우위)은 dev pilot에서 **기각**된다.

ISM은 keyword/oracle 수준(AR ~0.68)이며 summary보다 낮다. 6.1(심볼 구조·사전 의미내용의 기능적
사용)과 종합하면: **ISM의 가치는 토큰 효율이 아니라 검사·개입 가능성**이라는 해석이 dev-scale에서
지지된다. (full registered scale 확정은 후속.)

## 산출물 (Colab 보관, sha256)

| 파일 | sha256 |
|---|---|
| merged/fixed_budget_summary.json | `bb8ec2d9e5c0b5829ac4535dd40e4a7b8698c5b07b199dc39672a68e469b21a8` |
| merged/predictions.jsonl (1040줄) | `5115190974facbd36900f73ba54969d165788bf389ea9b70355dfcdc4c883b68` |
| merged/contexts.jsonl | `1bd812996fd9562330b28899c48235732b82ef57270715adf11fe6f757dccf03` |

## 재현
```bash
# Colab GPU (T4), commit 5d4500d
for off in 0 10 20 30; do
  python -m ism run-fixed-budget --config configs/experiments/fixed_budget_qwen7b_long.yaml \
    --output artifacts/runs/fb_pilot/shard$((off/10)) --doc-offset $off --doc-count 10 \
    --budgets 128 256 512 --methods full_context ism model_summary keyword_extract oracle_gold_summary --resume
done
python -m ism merge-fixed-budget --config configs/experiments/fixed_budget_qwen7b_long.yaml \
  --output artifacts/runs/fb_pilot/merged --shards artifacts/runs/fb_pilot/shard{0,1,2,3}
```
