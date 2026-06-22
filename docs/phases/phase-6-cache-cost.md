# Phase 6 완료 보고서: Reuse cache와 비용

## 1. 목표

Phase 6의 목표는 문서 압축을 질문과 독립적으로 한 번만 계산하고, cache 손상과 동시 접근에도
유효한 immutable artifact를 사용하며, serving 비용과 end-to-end 비용을 분리하는 것이다.

## 2. Cache 계약

- cache key는 document text와 compression 설정을 포함하고 question을 포함하지 않는다.
- 동일 key의 최초 요청만 compute를 실행한다.
- 다른 document text는 별도 key를 사용하며 같은 text는 공유할 수 있다.
- cache payload는 key digest, value, checksum을 함께 저장한다.
- checksum 또는 schema가 손상되면 `.corrupt`로 격리하고 재계산한다.
- 같은 key의 동시 writer는 file lock 안에서 재확인해 유효 파일 하나만 생성한다.
- write는 임시 파일, `fsync`, atomic replace 순서로 수행한다.
- hit, miss, corruption, write 수를 `CacheStats`에 기록한다.

## 3. 비용 계약

`serving_total_tokens`는 이미 생성된 representation으로 질문에 답하는 비용이다.

`end_to_end_total_tokens`는 serving 비용에 일회성 compression input/output을 더한다.

Full Context는 compression call과 compression token이 0이므로 두 비용이 같다.

## 4. 통과한 TC

| TC | 결과 |
|---|---|
| P6-FUN-001 문서당 compression 1회 | 통과 |
| P6-FUN-002 question-independent key | 통과 |
| P6-FUN-003 document text 격리 | 통과 |
| P6-FUN-004 hand-calculated cost formula | 통과 |
| P6-CON-001 serving/end-to-end 분리 | 통과 |
| P6-RES-001 checksum 손상 재계산 | 통과 |
| P6-RES-002 동시 cache writer | 통과 |
| P6-REG-001 질문 순서 비용 불변성 | 통과 |

Phase 0-5 회귀를 포함한 자동 테스트는 총 109개다.

## 5. 검증 결과

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pyright src tests
.venv/bin/pytest -m "not gpu and not network"
```

```text
Ruff: all checks passed
Formatting: 50 files already formatted
Pyright: 0 errors, 0 warnings
Pytest: 109 passed
Colab/GPU/API calls: 0
```

Cache fixture:

```text
10 sequential questions: compute=1, misses=1, hits=9
16 concurrent requests: compute=1, writes=1, hits=15
Corrupt checksum: corruptions=1, recompute=1
```

비용 fixture:

```text
document=1000, representation=100
questions=(10,20,30), answers=(2,2,2)
reasoning input=360, reasoning output=6
serving total=366
compression input=1000, compression output=100
end-to-end total=1466
```

## 6. 알려진 제한

- file locking은 POSIX `fcntl` 기반이며 Windows를 지원하지 않는다.
- cache eviction, 용량 quota, 원격 object storage는 구현하지 않았다.
- stats는 현재 process 메모리에 있으며 manifest writer 연결은 main orchestration 단계에서 수행한다.
- 비용 모델은 token 수를 계산하며 실제 GPU 시간과 금액 환산은 model benchmark 이후 가능하다.

## 7. Phase 7 진입 조건

- 질문 수와 무관하게 동일 문서 compression compute 1회
- cache 손상 사용 0, 재계산 성공
- concurrent writer compute/write 1회
- serving/end-to-end 비용 필드 분리
- 질문 순서에 비용 합계 독립
- 미해결 Blocking 오류 0

Phase 7에서는 label family 분리, leakage audit, LoRA train manifest/checkpoint 계약과 tiny local
trainer fixture를 구현한다.

## 8. Git 상태

이 보고서는 Phase 6 구현 직후, 해당 구현을 독립 커밋하기 전에 작성되었다.
