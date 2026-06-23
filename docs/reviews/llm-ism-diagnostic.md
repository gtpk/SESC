# LLM ISM Diagnostic — Δmap ≈ 0 원인 분석

- 날짜: 2026-06-23
- 동기: 6.1 Dictionary Ablation에서 Δmap = Acc(Full+Dict) − Acc(Corrupt) ≈ 0
  (LLM −0.028, gold 0.000). "사전을 망가뜨려도 성능이 안 떨어진다"의 원인 규명.
- 도구: [diagnostics.py](../../src/ism/experiments/diagnostics.py),
  `ism compress-audit` ([compression_audit.py](../../src/ism/experiments/compression_audit.py))
- 증거: [compress-audit](../evidence/compress-audit-qwen7b-dev/),
  [LLM ablation](../evidence/ablation-qwen7b-llm-dev/README.md),
  [gold ablation](../evidence/ablation-qwen7b-dev/README.md)

## 결론 (요약)

Δmap≈0은 **"ISM 가설이 틀렸다"가 아니라, 현재 셋업이 사전 사용을 시험할 수 없는 상태**임을
가리킨다. 원인은 둘이 겹쳐 있다.

1. **압축 품질(purity) 부족 — 1차 원인.** LLM 압축기가 규칙의 **조건은 남기고 결론(risk =
   HIGH/MEDIUM/LOW)을 버린다.** 따라서 ISM에 정답을 도출할 매핑이 자주 없다.
2. **corruption 설계가 내용 보존적 — 2차 원인.** `corrupt_dictionary`는 정의를 라벨 간
   derangement만 하므로 **정의 집합이 그대로**다(정보가 줄지 않음).

두 요인 모두 "사전을 망가뜨려도 답이 안 바뀐다"를 만든다. 즉 현재 Δmap은 사전 사용 여부를
측정하지 못한다.

## 측정값

| 지표 | gold ISM | **LLM ISM** | 함의 |
|---|---:|---:|---|
| rule_coverage (purity) | 1.00 | **0.70** | LLM이 gold 규칙의 ~30%를 누락 |
| self_containment | 1.00 | **0.71** | LLM 정의의 ~29%에 답 토큰(HIGH/LOW/True…) 없음 = **결론 누락** |
| relations_structure | 0.00 | **0.79** | LLM relations는 구조(`!`,순서)를 담음 (gold는 라벨 나열) |
| corruption_preserves_content | 1.00 | **1.00** | derangement는 정의 집합을 보존 → 정보량 불변 |
| mean_corruption_overlap | 0.37 | 0.30 | 라벨별 정의는 바뀌나 집합은 동일 |
| 압축 실패율 | – | **2/20** | §5.4 보고 대상 |
| majority baseline | 0.55 | 0.55 | 압축 조건 정확도(0.50)가 majority 근접 |

샘플 LLM ISM([sample_isms.md](../evidence/compress-audit-qwen7b-dev/sample_isms.md)):
`Z1 := marker_a = high and marker_b = low` 처럼 **조건만** 있고 `→ risk HIGH`가 없다.
일부 문서는 `Z1 !Z1` 같은 degenerate relation도 생성.

## 4축 진단 결과 (사용자 제안 체크리스트)

1. **압축 품질 audit** → purity 0.70, self_containment 0.71. **결론 누락이 핵심 결함.**
   압축 실패 2건. (relation leakage는 `parse_ism`의 leakage 검사로 차단됨.)
2. **Dictionary 사용성 probe** → corruption은 정의 집합을 보존(1.0)하므로 약하다.
   definition blanking은 symbol_only와 동치, adversarial-opposite는 미구현(아래 #2 fix).
3. **Reasoner behavior probe** → 현재 프롬프트가 답을 1단어로 강제해 chain-of-thought가
   없어 "정의 인용 여부"를 raw로 보기 어렵다. 별도 unconstrained probe 필요(후속).
4. **결론 분기** → 아래.

## 결론 분기 → 조치

- **purity가 낮다 → 압축기 개선(1차).** 압축 프롬프트/스키마를 고쳐 정의가 **조건과 결론을
  함께** 담도록 한다(예: `Z1 := if marker_a high and marker_b low then risk HIGH`).
  목표: self_containment·rule_coverage ↑.
- **corruption이 약하다 → intervention 강화(2차).** label derangement 대신 **내용 변경형**
  corruption 추가: (a) 결론값 반전(HIGH↔LOW), (b) definition blanking. 새 조건으로 6.1 재실행.
- 위 두 가지를 고친 뒤에야 Δmap이 사전 사용 여부를 **유효하게** 측정한다. 그 전에는 6.2/6.3로
  넘어가지 않는다(해석 불가).

## 다음 작업 (제안 순서)

1. 압축기 프롬프트/스키마 개선 → compress-audit로 purity·self_containment 재측정(빠름).
2. 내용 변경형 corruption(결론 반전) 구현 + 단위 테스트.
3. 6.1 재실행(LLM 압축기 + 강한 corruption), §8.1.1 갱신.
4. (후속) unconstrained reasoner probe로 정의 인용 여부 직접 확인.

## 2026-06-23 후속 조치: 압축기 self-containment gate

첫 번째 조치를 구현했다.

- compression prompt에 "각 dictionary 정의는 trigger condition과 resulting conclusion/outcome을
  모두 포함해야 한다"는 제약을 추가했다.
- `parse_ism`을 통과한 뒤에도 `definition_self_containment(representation) < 1.0`이면 유효한
  압축으로 보지 않고 `missing_conclusion_tokens` nudge로 재생성한다.
- 형식은 맞지만 `Z1 := marker_a high and marker_b low`처럼 결론이 빠진 출력은 더 이상 6.1
  ablation에 들어가지 않는다.
- 관련 offline TC를 추가했고 전체 로컬 회귀는 185개 통과했다.

다음 판단 기준:

- `compress-audit`에서 LLM ISM의 `mean_self_containment`가 1.0에 가까워져야 한다.
- 이 gate 이후에도 `rule_coverage`가 낮으면 prompt만이 아니라 출력 schema나 few-shot 예시를 더
  강화해야 한다.
- self-containment와 coverage가 개선된 뒤에도 Δmap≈0이면, 그때는 2차 원인인 corruption 설계를
  내용 변경형으로 강화해 다시 측정한다.
