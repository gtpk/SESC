# Evidence — Experiment 6.1 Dictionary Ablation (LLM compressor, dev pilot)

논문 **메인 설정**(LLM 압축기)으로 수행한 RQ1 ablation의 예비 결과. gold-oracle 버전은
[../ablation-qwen7b-dev/](../ablation-qwen7b-dev/README.md) 참조.

## 설정

| 항목 | 값 |
|---|---|
| config | [configs/experiments/ablation_qwen7b.yaml](../../../configs/experiments/ablation_qwen7b.yaml) |
| config_hash | `204d4b4b7061495dce29d7fa86021deacd8e94be5ac0cc885e403ca6e239f00f` |
| code commit | `eb2bdda24e02156f6de2fe714a234de9a8f21012` |
| 압축기/추론기 | Qwen2.5-7B-Instruct 4-bit (동일 모델), greedy, seed 42, T4 |
| ISM 출처 | **LLM 압축기 산출물** → `parse_ism`으로 구조화 (논문 §3.3) |
| 압축 | 20 문서 중 **18 성공 / 2 실패**, mean_attempts 1.06 |
| 규모 | 18 docs × 2 questions × 5 conditions = 180 predictions (0 errors), N=36 문항 |
| 소요 | 596.7s |

## 결과

| 조건 | Accuracy | AR | CR | ES |
|---|---:|---:|---:|---:|
| Full Context | 0.694 | 1.000 | 1.000 | 1.000 |
| Full Symbol + Dict | 0.500 | 0.720 | 0.562 | 1.280 |
| Corrupted Dict | 0.528 | 0.760 | 0.562 | 1.352 |
| Symbol Only | 0.361 | 0.520 | 0.109 | 4.770 |
| Random Symbol | 0.333 | 0.480 | 0.555 | 0.865 |

- **Δmap** = Acc(Full+Dict) − Acc(Corrupt) = **−0.028**, 95% CI [−0.167, 0.083], McNemar p=1.0 (n=36)
- **Δsymbol** = Acc(SymbolOnly) − Acc(Random) = **+0.028**, 95% CI [−0.139, 0.194], McNemar p=1.0 (n=36)

## 해석 (예비)

- **Δmap ≈ 0** (CI가 0 포함, 오히려 corrupted가 약간 높음): LLM 압축기 산출물에서도
  **사전 정의 오염이 정확도를 떨어뜨리지 않는다.** gold-oracle 파일럿과 동일한 방향 →
  "모델이 사전 매핑을 기능적으로 사용한다"는 근거가 (이 규모에서) 관찰되지 않음.
- **Δsymbol = +0.028** (비유의): Symbol Only가 Random보다 약간 높지만 CI가 0을 포함.
- 즉 부록 A 기준 #2는 **이 dev 파일럿에서 충족되지 않는다**(gold·LLM 양쪽 일관).

차이점: LLM 압축기는 gold보다 더 압축한다(Full+Dict CR 0.562 vs gold 0.818). 압축 실패율
10%(2/20)는 §5.4 보고 대상이다.

### 한계 (gold 파일럿과 공통)

N=36·단일 seed로 CI가 넓다(±0.15 수준). 등록 규모(dev 5k) 실행 전에는 RQ1 결론을 내리지
않는다. 비교군(model_summary/keyword_extract/llmlingua_2)은 여전히 미구현으로 제외.

## 파일

| 경로 | 내용 |
|---|---|
| `ablation_summary.json` | 조건별 AR/CR/ES + Δmap/Δsymbol + 압축 통계 |
| `SHA256SUMS` | summary + predictions(180줄)·condition_audit(180레코드, Colab 보관) sha256 |
| `environment.json` | commit, GPU |

## 재현

```bash
# Colab GPU (T4+), commit eb2bdda
pip install -e ".[gpu]"
python -m ism run-ablation --config configs/experiments/ablation_qwen7b.yaml \
  --output artifacts/runs/ablation --batch-size 1
# backend=transformers 이므로 LLM 압축기 경로가 자동 사용됨
```
