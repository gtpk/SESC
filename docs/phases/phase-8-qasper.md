# Phase 8 완료 보고서: QASPER adapter

## 1. 목표

Phase 8의 목표는 QASPER 원본 paper/question/answer/evidence 구조를 공통 dataset contract로
결정적으로 변환하고, malformed 항목과 test tuning을 안전하게 격리하는 것이다.

QASPER 공식 논문의 task 정의에 따라 extractive, abstractive, yes/no, unanswerable 답과 다중
evidence를 지원한다. split은 paper 단위로 외부에서 주입하며 문서 ID를 변경하지 않는다.

## 2. 구현 계약

- title, abstract, section, paragraph, question, 다중 answer를 내부 record로 보존한다.
- yes/no는 `Yes`/`No`, unanswerable은 `Unanswerable`로 정규화한다.
- extractive span은 comma-separated answer text로 유지한다.
- evidence는 원문 text, character start/end, section, paragraph index를 기록한다.
- paper와 question ID는 원본 ID를 사용해 reload 후에도 동일하다.
- malformed question은 quarantine하고 같은 paper의 정상 question 로드를 계속한다.
- malformed paper는 document-level quarantine으로 격리한다.
- `test + tuning_mode` 조합은 거부한다.
- Synthetic과 QASPER는 동일 `QuestionRecord`/`AnswerRecord` contract를 사용한다.

## 3. 통과한 TC

| TC | 결과 |
|---|---|
| P8-CON-001 source schema mapping | 통과 |
| P8-CON-002 stable document/question IDs | 통과 |
| P8-FUN-001 four answer type normalization | 통과 |
| P8-FUN-002 evidence offset/section linkage | 통과 |
| P8-ERR-001 malformed question quarantine | 통과 |
| P8-CFG-001 test tuning protection | 통과 |
| P8-REG-001 20-question golden adapter digest | 통과 |
| Synthetic common QuestionRecord conversion | 통과 |

Phase 0-7 회귀를 포함한 자동 테스트는 총 126개다.

## 4. 검증 결과

```text
Ruff: all checks passed
Formatting: 56 files already formatted
Pyright: 0 errors, 0 warnings
Pytest: 126 passed
Colab/GPU/API calls: 0
```

20문항 golden digest:

```text
3036aaf34ac7274e66de890c86ed5683c0e8a4816b1a7a9dc14f15f4ad2d60af
```

## 5. 알려진 제한

- 테스트는 공식 task 정의를 반영한 offline fixture이며 전체 QASPER 파일은 아직 다운로드하지 않았다.
- figure/table evidence는 현재 multimodal asset linkage를 구현하지 않았으며 text evidence 중심이다.
- 동일 evidence paragraph가 문서에 반복될 경우 최초 위치를 사용한다.
- 실제 train/dev/test 파일 간 paper ID 교집합 audit는 데이터 다운로드 후 Phase 9에서 수행한다.

## 6. Phase 9 진입 조건

- 원본 core field와 answer type 보존
- evidence source offset 검증
- malformed item 격리
- test tuning 거부
- 20문항 golden 변환 고정
- Synthetic/QASPER 공통 question contract
- 미해결 로컬 Blocking 오류 0

Phase 9에서는 frozen run manifest, metric/statistics, report generation, 비용 승인, Colab MCP 환경
smoke와 제한 pilot을 수행한다.

## 7. Git 상태

이 보고서는 Phase 8 구현 직후, 해당 구현을 독립 커밋하기 전에 작성되었다.
