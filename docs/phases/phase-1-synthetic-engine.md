# Phase 1 완료 보고서: Synthetic engine

## 1. 목표

Phase 1의 목표는 외부 모델과 GPU 없이 논리 규칙 문서, 정답, 질문을 결정적으로 생성하고
손실 없이 저장할 수 있는 synthetic engine을 만드는 것이었다.

구현 범위:

- 정규화된 fact, condition, rule, graph schema
- conjunction, disjunction, exception, precedence, threshold, temporal executor
- fixed-point 실행, 충돌 및 cycle 검출
- 자연어 renderer와 질문/정답 생성
- atomic JSONL 저장과 엄격한 복원
- 설정 기반 `generate-synthetic` CLI
- golden, 결정성, 오류, 스트레스 TC

실제 LLM 압축과 ISM parser/intervention은 이 Phase의 범위가 아니다.

## 2. 환경

| 항목 | 값 |
|---|---|
| Python | 3.14.3 |
| 실행 환경 | 로컬 CPU |
| 외부 API | 사용하지 않음 |
| Colab/GPU 사용 | 없음 |
| 생성기 버전 | 0.1.0 |

## 3. 구현 파일

| 경로 | 역할 |
|---|---|
| `src/ism/data/rules.py` | graph schema, validation, deterministic executor |
| `src/ism/data/render.py` | graph의 자연어 직렬화 |
| `src/ism/data/generator.py` | seeded 문서와 질문 생성 |
| `src/ism/data/io.py` | atomic JSONL export/import |
| `src/ism/cli.py` | 설정 기반 `generate-synthetic` 명령 |
| `tests/test_rules.py` | 규칙 의미론, 충돌, cycle, 오류 TC |
| `tests/test_generator.py` | 결정성, golden, ID, renderer TC |
| `tests/test_data_io.py` | 손상 진단과 round-trip TC |

## 4. 구현된 계약

### Graph 계약

- 모든 model은 immutable이며 알 수 없는 필드를 거부한다.
- rule ID와 초기 fact key는 graph 안에서 유일해야 한다.
- exception은 존재하는 rule만 참조할 수 있다.
- threshold와 temporal rule은 종류별 필수 필드를 검증한다.
- 숫자가 아닌 값의 수치 비교는 묵시 변환하지 않고 오류로 거부한다.

### 실행 계약

- 같은 graph와 fact는 항상 같은 결과와 fired rule 순서를 만든다.
- exception은 base rule뿐 아니라 다른 exception도 명시적으로 억제할 수 있다.
- 동일 priority에서 서로 다른 값을 도출하면 임의 선택하지 않고 conflict 오류를 낸다.
- dependency cycle과 fixed-point 비수렴은 제한된 실행 안에서 오류로 종료한다.
- renderer와 intervention 전 단계는 입력 graph를 변경하지 않는다.

### 저장 계약

- JSONL은 같은 디렉터리의 임시 파일에 기록하고 `fsync` 후 교체한다.
- 손상된 JSON은 파일명과 1-based line 번호를 포함해 보고한다.
- graph, answer, required rule ID, generator version, seed를 round-trip 보존한다.

## 5. 통과한 TC

| TC | 결과 |
|---|---|
| P1-CON-001 graph schema round-trip | 통과 |
| P1-FUN-001 conjunction truth table | 통과 |
| P1-FUN-002 disjunction truth table | 통과 |
| P1-FUN-003 exception 우선순위와 exception-to-exception | 통과 |
| P1-FUN-004 equal-priority conflict rejection | 통과 |
| P1-FUN-005 threshold 경계 | 통과 |
| P1-FUN-006 temporal ordering | 통과 |
| P1-DET-001 동일 seed 결정성 | 통과 |
| P1-DET-002 다른 seed 구분 | 통과 |
| P1-CON-002 문서·질문 ID 유일성 | 통과 |
| P1-ERR-001 결정 불가능 수치 graph 거부 | 통과 |
| P1-ERR-002 dependency cycle 거부 | 통과 |
| P1-IO-001 손상 JSONL line 진단 | 통과 |
| P1-IO-002 export/import 보존 | 통과 |
| P1-REG-001 20 graph와 100 answer golden hash | 통과 |
| 전체 RuleKind 생성기 포함 | 통과 |
| renderer 입력 불변성 | 통과 |
| CLI 실제 JSONL 생성 | 통과 |

Phase 0 회귀를 포함한 자동 테스트는 총 44개다.

## 6. 검증 결과

실행 명령:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pyright src tests
.venv/bin/pytest -m "not gpu and not network"
.venv/bin/python -m ism generate-synthetic \
  --config configs/experiments/smoke.yaml \
  --output /tmp/ism-phase1-smoke.jsonl
```

결과:

```text
Ruff: all checks passed
Formatting: 19 files already formatted
Pyright: 0 errors, 0 warnings
Pytest: 44 passed
CLI smoke: 3 documents, 6 questions
```

## 7. 10,000문서 스트레스

seed 42, dev split에서 로컬 CPU로 실행했다.

| 항목 | 결과 |
|---|---|
| 문서 | 10,000 |
| 질문 | 20,000 |
| 생성 시간 | 0.733초 |
| JSONL 크기 | 48,666,277 bytes |
| JSONL SHA-256 | `93ac92449f00b0646cc3b4acb0c6c7e2446a27d8e0fc6795dbd730dfc9c97ff0` |
| export/import 동등성 | true |
| document ID 충돌 | 0 |
| question ID 충돌 | 0 |

## 8. 발견한 문제와 수정

### exception이 다른 exception을 억제하지 못함

초기 executor는 exception rule을 억제 대상 필터에서 무조건 제외했다. 따라서
exception-to-exception 관계를 schema가 허용하면서 실행기는 무시하는 모순이 있었다. 모든 rule
종류에 동일한 억제 필터를 적용하고 회귀 TC를 추가했다.

### 생성기가 선언된 RuleKind 일부를 만들지 않음

초기 생성기는 6종 중 exception과 precedence를 포함하지 않았다. 두 규칙을 기본 graph에 추가하고
생성된 graph의 종류 집합이 `RuleKind` 전체와 같은지 검사한다.

### CLI 설정 경로 불일치

첫 통합 실행은 `config.seed`와 `dataset.split`을 잘못 참조했다. 실제 schema의
`experiment.seed`, `experiment.split`으로 수정했고 subprocess CLI TC로 고정했다.

## 9. 알려진 제한

- 현재 template은 한 도메인과 문서당 두 질문만 생성한다.
- required rule ID는 질문별 최소 proof가 아니라 해당 graph 실행에서 fire된 rule 집합이다.
- golden은 생성기 0.1.0의 구조를 고정하므로 의도적인 schema 변경 시 명시적으로 갱신해야 한다.
- 자연어 표현의 다양성과 OOD split 생성은 후속 데이터 확장 단계에서 보강한다.
- 대규모 스트레스 파일은 `/tmp`에 생성했으며 Git artifact로 보존하지 않는다.

## 10. Phase 2 진입 조건

Phase 2 시작 조건은 충족됐다.

- Phase 1 Blocking TC 전부 통과
- 10,000문서 stress에서 crash와 ID 충돌 0
- JSONL round-trip과 atomic replace 통과
- 지원하는 6종 규칙이 실제 생성 경로에 포함됨
- 외부 API, GPU, Colab 비용 0
- 미해결 Blocking 오류 0

Phase 2에서는 ISM schema, parser/serializer, token budget 검증, dictionary removal/corruption,
random control, label swap, leakage validator를 구현한다.

## 11. 재현 절차

```bash
uv sync --dev
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pyright src tests
.venv/bin/pytest -m "not gpu and not network"
.venv/bin/python -m ism generate-synthetic \
  --config configs/experiments/smoke.yaml \
  --output /tmp/ism-phase1-smoke.jsonl
```

## 12. Git 상태

이 보고서는 Phase 1 구현 직후, 해당 구현을 독립 커밋하기 전에 작성되었다.
