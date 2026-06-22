# Phase 7 완료 보고서: Swap training local contract

## 1. 목표

Phase 7의 로컬 목표는 실제 7B LoRA 학습 전에 label split, leakage, train manifest, checkpoint,
resume, 2x2 평가 행렬의 코드 계약을 GPU 없이 검증하는 것이다.

## 2. 구현 계약

- train/dev/test label family는 내부 중복과 상호 교집합이 없어야 한다.
- 각 split의 raw text에서 다른 split label 출현을 audit할 수 있다.
- LoRA config는 base model/revision, tokenizer revision, rank, alpha, dropout, seed를 포함한다.
- checkpoint는 base revision, global step, parameter, optimizer momentum, scheduler scale, loss를
  원자적으로 저장한다.
- 다른 base revision의 checkpoint resume를 거부한다.
- local tiny trainer는 중단/재개와 연속 학습이 동일한 state를 만든다.
- 2x2 swap matrix 네 조건은 동일 question set을 사용한다.
- eval-only checkpoint load는 trainer 실행 없이 가능하다.

## 3. 통과한 TC

| TC | 결과 |
|---|---|
| P7-CON-001 label family disjoint | 통과 |
| P7-CON-002 raw text label leakage | 통과 |
| P7-CFG-001 LoRA manifest 완전성 | 통과 |
| P7-RES-001 optimizer/scheduler/step resume | 통과 |
| P7-RES-002 base revision mismatch rejection | 통과 |
| P7-IO-001 atomic complete JSON checkpoint | 통과 |
| P7-INT-001 tiny trainer loss 감소와 round-trip | 통과 |
| P7-INT-002 2x2 aligned matrix | 통과 |
| P7-ENV-001 eval-only checkpoint load | 통과 |

Phase 0-6 회귀를 포함한 자동 테스트는 총 118개다.

## 4. 검증 결과

```text
Ruff: all checks passed
Formatting: 53 files already formatted
Pyright: 0 errors, 0 warnings
Pytest: 118 passed
Colab/GPU/API calls: 0
```

## 5. 범위 구분

완료된 것은 LoRA 실험의 로컬 코드 계약이다. `TinySwapTrainer`는 checkpoint와 resume 의미론을
검증하는 수치 fixture이며 실제 PEFT/LoRA 모델 학습 결과가 아니다.

Colab에서 남은 작업:

- Transformers, PEFT, bitsandbytes adapter 구현
- 7B 4-bit model load smoke
- tiny real batch overfit
- adapter save/load와 eval-only inference
- GPU memory, latency, checkpoint artifact 기록

이 작업은 로컬 TC를 대체하지 않고 Phase 9 서버 실행에서 별도 검증한다.

## 6. Phase 8 진입 조건

- label family overlap 0
- train raw text test label leakage 0
- checkpoint resume state 동등성
- revision mismatch 거부
- 2x2 question alignment
- 미해결 로컬 Blocking 오류 0

Phase 8에서는 QASPER source mapping, answer type 보존, evidence offset, split 경계, offline fixture
adapter를 구현한다.

## 7. Git 상태

이 보고서는 Phase 7 로컬 계약 구현 직후, 해당 구현을 독립 커밋하기 전에 작성되었다.
