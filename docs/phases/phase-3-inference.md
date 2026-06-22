# Phase 3 완료 보고서: Inference pipeline

## 1. 목표

Phase 3의 목표는 모델 backend와 실험 실행 로직을 분리하고, 중단·재시도·부분 실패에도 유효한
artifact를 남기는 로컬 CPU inference pipeline을 만드는 것이다.

구현 범위:

- `TextGenerator` Protocol과 엄격한 generation request/result schema
- 성공·transient·OOM·validation·fatal 결과 계약
- adapter와 무관한 batch/retry runner
- atomic prediction store와 duplicate 방지
- checkpoint 이후 resume와 완료 sample skip
- document-level compression cache key
- synthetic dataset부터 metrics/manifest까지 mock end-to-end CLI

실제 Transformers와 GPU model loading은 로컬 계약을 그대로 구현하는 후속 adapter 범위다.

## 2. 구현 파일

| 경로 | 역할 |
|---|---|
| `src/ism/inference/contracts.py` | request/result와 `TextGenerator` Protocol |
| `src/ism/inference/mock.py` | 성공과 계획된 실패를 만드는 CPU mock adapter |
| `src/ism/inference/errors.py` | OOM/transient/validation/fatal 분류 |
| `src/ism/inference/cache.py` | compression cache key |
| `src/ism/inference/runner_models.py` | sample과 prediction record |
| `src/ism/inference/artifacts.py` | atomic JSONL prediction store |
| `src/ism/inference/runner.py` | batch, retry, resume orchestration |
| `src/ism/inference/pipeline.py` | dataset-to-metrics local pipeline |
| `src/ism/cli.py` | `run-mock` 명령 |

## 3. Adapter 계약

- runner는 구체 model class를 import하거나 생성하지 않는다.
- adapter는 요청마다 정확히 하나의 `GenerationResult`를 반환한다.
- 성공 결과는 text를 포함하고 error를 포함하지 않는다.
- 실패 결과는 error kind/message를 포함하고 partial text를 포함하지 않는다.
- 누락, 추가, 중복 request ID는 runner가 즉시 거부한다.
- sample ID는 adapter request ID로 유일해야 한다.

## 4. Retry와 failure 계약

- transient failure만 설정된 최대 횟수까지 재시도한다.
- OOM, validation, fatal은 같은 batch의 다른 sample과 분리해 즉시 기록한다.
- retry 소진은 예외로 전체 run을 버리지 않고 failure prediction을 저장한다.
- 각 prediction은 실제 attempt 수와 error kind/message를 보존한다.
- batch size가 달라도 sample별 결과와 최종 순서는 같다.

## 5. Artifact와 resume 계약

- prediction은 임시 파일에 전체 유효 JSONL을 기록하고 `fsync` 후 원자 교체한다.
- 교체 전 중단되면 기존 artifact가 byte-identical하게 유지된다.
- `(sample_id, condition)` 중복은 저장 시 거부한다.
- `resume=False`에서 기존 artifact를 덮어쓰지 않는다.
- `resume=True`는 완료 key를 건너뛰고 미완료 sample만 adapter에 전달한다.
- 완료된 run의 두 번째 resume는 adapter 호출 0회다.

## 6. Cache key 계약

compression cache digest는 다음을 포함한다.

- document text
- method
- budget
- prompt version
- model ID와 revision
- tokenizer revision
- decoding config

질문은 document-independent compression key에 포함하지 않는다.

## 7. 통과한 TC

| TC | 결과 |
|---|---|
| P3-ARC-001 MockA/MockB adapter 치환 | 통과 |
| P3-CON-001 success/failure result schema | 통과 |
| P3-INT-001 dataset-to-metrics CLI | 통과 |
| P3-INT-002 batch 1/N 동등성 | 통과 |
| P3-RES-001 중간 중단 후 complete record만 보존 | 통과 |
| P3-RES-002 resume 완료 sample 호출 0 | 통과 |
| P3-RES-003 transient retry 성공 | 통과 |
| P3-RES-004 retry 소진 failure 저장 | 통과 |
| P3-IO-001 atomic replace interruption | 통과 |
| P3-IO-002 duplicate prediction 방지 | 통과 |
| P3-CFG-001 cache key 완전성 | 통과 |
| P3-CFG-002 question-independent cache key | 통과 |
| P3-ERR-001 OOM 분류 | 통과 |
| P3-ERR-002 partial batch failure 격리 | 통과 |
| P3-ENV-001 CPU mock import/run | 통과 |
| adapter request ID collision rejection | 통과 |

Phase 0-2 회귀를 포함한 자동 테스트는 총 83개다.

## 8. 검증 결과

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pyright src tests
.venv/bin/pytest -m "not gpu and not network"
.venv/bin/python -m ism run-mock \
  --config configs/experiments/smoke.yaml \
  --output /tmp/ism-phase3-smoke \
  --batch-size 4
.venv/bin/python -m ism run-mock \
  --config configs/experiments/smoke.yaml \
  --output /tmp/ism-phase3-smoke \
  --batch-size 2 \
  --resume
```

```text
Ruff: all checks passed
Formatting: 40 files already formatted
Pyright: 0 errors, 0 warnings
Pytest: 83 passed
Initial CLI: 3 documents, 6 questions, 18 predictions
Resume CLI: 18 predictions, duplicate 0
Accuracy: 1.0 (mock expected-output adapter)
Colab/GPU/API calls: 0
```

생성 artifact:

- `predictions.jsonl`: 18줄
- `metrics.json`: 성공, 정답 수, 정확도
- `manifest.json`: config hash, revision, seed, split, conditions, status

## 9. 발견한 문제와 수정

### condition key와 adapter request ID의 유일성 차이

runner는 `(sample_id, condition)`을 저장 key로 사용하지만 내부 request map은 `sample_id`로
구성한다. 동일 sample ID를 여러 condition에서 재사용하면 map이 덮어써질 수 있어, public 입력에서
adapter request ID의 전역 유일성을 별도로 검증하고 회귀 TC를 추가했다.

### 전체 run 실패와 sample 실패의 혼용 위험

adapter failure를 예외로 던지면 한 sample의 OOM이 전체 batch를 잃게 된다. 실패도
`GenerationResult`로 반환하도록 계약을 고정해 sample 단위로 격리했다. adapter 자체의 계약 위반은
run-level 오류로 유지한다.

## 10. 알려진 제한

- mock adapter는 `expected_output`을 반환하므로 모델 정확도 검증 용도가 아니다.
- 현재 store는 매 checkpoint에 전체 JSONL을 재작성해 소규모/중간 run에 적합하다.
- 실제 Transformers tokenizer/model adapter와 GPU memory telemetry는 아직 없다.
- process-level file lock은 없으며 병렬 writer cache는 Phase 6에서 구현한다.
- manifest의 started/completed timestamp와 git commit 자동 기록은 후속 orchestration에서 추가한다.

## 11. Phase 4 진입 조건

- Phase 3 Blocking TC 전부 통과
- runner에서 구체 backend import/생성 없음
- 동일 완료 run의 resume adapter 호출 0
- partial failure가 다른 sample 결과를 제거하지 않음
- mock dataset-to-metrics CLI 통과
- 외부 API, GPU, Colab 비용 0
- 미해결 Blocking 오류 0

Phase 4에서는 조건별 입력 생성, source compression linkage, paired alignment, condition audit와
3문서 golden ablation run을 구현한다.

## 12. Git 상태

이 보고서는 Phase 3 구현 직후, 해당 구현을 독립 커밋하기 전에 작성되었다.
