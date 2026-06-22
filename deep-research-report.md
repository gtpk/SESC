# Inspectable Symbolic Compression for Long-Context Reasoning

## 장문 추론을 위한 검사·개입 가능한 이산 심볼 압축

> **논문 초안 상태:** 실험 전 원고. 대괄호로 표시된 값과 결과 서술은 실험 완료 후 채운다.

## 초록

대규모 언어 모델의 장문 추론 비용을 줄이기 위한 기존 연구는 원문에서 중요한 토큰을 선택하거나 문맥을 연속 벡터로 압축해 왔다. 그러나 압축된 표현이 어떤 정보를 보존하는지, 그리고 그 의미 매핑에 직접 개입할 수 있는지는 충분히 검증되지 않았다. 본 논문은 긴 문서를 재사용 가능한 이산 텍스트 심볼과 짧은 사전으로 변환하는 **Inspectable Symbolic Compression (ISM)** 을 제안한다. ISM은 문서를 `Z1`, `Z2`, ... 형태의 심볼 집합으로 압축하며, 각 심볼의 의미를 명시하는 사전을 선택적으로 제공한다. 이 표현은 실제 토큰으로 구성되므로 압축 비용을 직접 측정할 수 있고, 사전 제거·오염 및 심볼 라벨 교환을 통해 표현의 기능을 통제된 방식으로 검사할 수 있다.

우리는 네 가지 연구 질문을 평가한다. 첫째, 심볼과 사전이 실제로 추론에 사용되는가. 둘째, 모델은 특정 심볼 문자열을 암기하는 대신 새로운 라벨과 의미의 결합을 사용할 수 있는가. 셋째, ISM은 동일 토큰 예산에서 자연어 요약과 기존 프롬프트 압축보다 더 많은 과제 관련 정보를 보존하는가. 넷째, 한 번 압축한 표현을 다수의 질문에 재사용할 때 정확도와 비용 특성이 어떻게 변하는가. 이를 위해 잠재 규칙 구조가 알려진 Synthetic Rule-QA와 실제 학술 문서 질의응답 데이터셋 QASPER를 사용한다. 메인 실험은 고정된 압축기와 추론기의 prompt-only 설정에서 수행하며, 라벨 교환 실험에만 소규모 LoRA 학습을 사용한다. 정확도 보존율, 압축률, 효율 점수, 교환 강건성 및 ablation 민감도를 paired evaluation으로 측정한다. 본 연구는 압축률뿐 아니라 **표현에 대한 개입 가능성**을 장문 문맥 압축의 평가 축으로 제시한다.

**주제어:** long-context reasoning, prompt compression, discrete representation, intervenability, large language models

## 1. 서론

대규모 언어 모델은 긴 문서, 검색 결과, 대화 이력을 입력으로 받아 복잡한 질의에 답할 수 있지만, 입력 길이가 증가할수록 추론 비용과 지연 시간도 함께 증가한다. 이 문제를 완화하기 위해 Selective Context와 LLMLingua 계열은 중요도가 낮은 텍스트를 제거하고 [7–10], Gist Tokens, AutoCompressors, ICAE와 같은 방법은 긴 문맥을 소수의 연속 메모리 표현으로 압축한다 [11–13]. 이러한 방법은 높은 압축률에서도 상당한 성능을 유지할 수 있음을 보여주었다.

그러나 기존 평가의 대부분은 압축 전후의 정확도와 토큰 수에 집중한다. 압축 결과가 실제로 어떤 정보 단위를 담는지, 그 정보 단위의 의미를 변경했을 때 추론 결과가 어떻게 달라지는지는 상대적으로 덜 연구되었다. 토큰 선택 방식은 남은 원문을 사람이 읽을 수 있지만 독립적인 의미 단위를 제공하지 않으며, 연속 메모리는 높은 표현력을 갖는 대신 개별 요소의 의미를 제거하거나 교환하기 어렵다. 따라서 압축 표현의 성능과 그 내부 작동 방식을 함께 평가하기 위한 중간 표현이 필요하다.

본 논문은 긴 문서를 짧은 이산 텍스트 심볼과 사전으로 변환하는 **Inspectable Symbolic Compression (ISM)** 을 제안한다. 예를 들어 조건부 규칙은 `Z1: marker_a high & marker_b low -> risk+`와 같이 표현된다. 이러한 표현은 자연어보다 조밀하지만 일반 토큰으로 구성되며, 심볼과 의미의 대응 관계가 외부에 명시된다. 이 구조 덕분에 정상 사전을 제거하거나, 잘못된 의미를 연결하거나, 기존 라벨을 학습에서 보지 못한 라벨로 교환하는 개입을 수행할 수 있다.

ISM의 목표는 이산 심볼이 모든 연속 압축 방식보다 우수하다고 주장하는 것이 아니다. 본 연구의 핵심 가설은 **경쟁적인 정보 보존 효율을 갖는 동시에 조작 가능한 압축 표현을 만들 수 있다**는 것이다. 이 가설을 검증하기 위해 정답 생성 규칙을 완전히 추적할 수 있는 합성 데이터에서 원인 분석과 심볼 교환 실험을 수행하고, QASPER에서 실제 자연어 문서에 대한 외적 타당도를 평가한다.

본 논문의 기여는 다음과 같다.

1. 긴 문서를 사전이 결합된 이산 텍스트 심볼로 압축하는 ISM을 정식화한다.
2. 사전 제거, 사전 오염, 무작위 심볼 및 미관측 라벨 교환을 포함하는 개입 기반 평가 프로토콜을 제안한다.
3. 동일한 64–512 토큰 예산에서 자연어 요약, 키워드 추출 및 LLMLingua-2와 정보 보존 효율을 비교한다.
4. Synthetic Rule-QA와 QASPER를 역할에 따라 분리하여 원인 분석과 실제 문서 타당도를 각각 평가한다.

본 연구의 주장은 위 범위로 제한한다. ISM을 새로운 언어, 모델의 의식, 세계모델 또는 인간과 동일한 개념 형성의 증거로 해석하지 않는다.

## 2. 관련 연구

### 2.1 프롬프트 및 문맥 압축

Hard prompt compression은 입력에서 과제 수행에 중요한 텍스트를 선택해 토큰 수를 줄인다. Selective Context는 정보량을 기준으로 덜 중요한 어휘 단위를 제거하며 [10], LLMLingua는 작은 언어 모델을 이용한 coarse-to-fine 압축을 제안했다 [7]. LongLLMLingua는 장문 환경에서 질문과 문맥 사이의 관련성을 반영했고 [8], LLMLingua-2는 데이터 증류를 통해 범용 압축 모델을 학습했다 [9]. 이 방법들은 ISM의 Fixed-Budget 실험에서 가장 직접적인 비교군이다.

ISM은 원문의 일부를 그대로 선택하는 대신 규칙과 관계를 심볼-사전 구조로 재표현한다. 따라서 압축 정확도 외에 특정 의미 단위의 제거와 교환을 평가할 수 있다는 차이가 있다.

### 2.2 연속 문맥 압축

Gist Tokens는 프롬프트를 소수의 gist token에 압축해 재사용하는 방법을 제안했고 [11], AutoCompressors는 긴 문맥을 summary vector로 변환했다 [12]. ICAE는 문맥을 memory slot으로 인코딩하며 [13], PCC와 xRAG는 독립 압축기 또는 검색 임베딩을 이용한 고비율 압축을 탐구했다 [14, 15].

연속 표현은 높은 정보 용량을 제공하지만, 메모리 슬롯 하나가 어떤 의미를 담당하는지 명시적으로 정의되지 않는 경우가 많다. 또한 실제 텍스트 토큰과의 비용 비교에는 KV-cache 또는 등가 토큰 환산이 필요하다. ISM은 표현력을 일부 포기하는 대신 실제 토큰 길이와 명시적 사전을 사용한다. 따라서 연속 압축의 대체재라기보다, 검사 가능성을 우선한 상보적 설계로 볼 수 있다.

### 2.3 개념 병목과 개입 가능한 표현

Concept Bottleneck Models는 입력과 최종 예측 사이에 사람이 정의한 개념층을 배치해 개념 수준의 수정과 오류 분석을 가능하게 했다 [1]. 이후 Concept Embedding Models, generative CBM, open-vocabulary CBM은 개념 표현의 유연성과 적용 범위를 확장했다 [2–4]. Discover-then-Name은 사전 정의된 개념에 의존하지 않고 특징을 발견한 후 이름을 부여하는 방향을 제안했으며 [5], Concept Bottleneck LLM은 이러한 중간 표현을 언어 모델에 적용했다 [6].

ISM은 중간 표현에 개입한다는 점에서 이 계열과 연결된다. 그러나 개념 감독을 통한 예측 설명이 아니라, 제한된 토큰 예산에서 장문 정보를 보존하는 것이 일차 목표다. 메인 실험에서 별도의 개념 분류기를 학습하지 않는다는 점도 다르다.

### 2.4 연구 간극

기존 연구는 압축 효율과 해석 가능한 중간 표현을 각각 발전시켜 왔다. 본 연구는 두 흐름 사이에서 다음 질문을 다룬다.

> 이산 텍스트 압축 표현이 장문 추론에 필요한 정보를 보존하면서, 그 의미 매핑에 대한 개입에도 예측 가능한 반응을 보이는가?

이 질문에 답하기 위해 성능 비교만이 아니라 표현의 구성 요소를 직접 변경하는 ablation과 swap을 핵심 실험으로 사용한다.

## 3. Inspectable Symbolic Compression

### 3.1 문제 정의

문서 \(x\), 질문 \(q\), 정답 \(y\)가 주어졌다고 하자. 압축기 \(C\)는 문서 \(x\)를 압축 표현 \(z\)로 변환하고, 추론기 \(R\)은 \(z\)와 \(q\)로부터 정답을 생성한다.

\[
z = C(x; B), \qquad \hat{y} = R(z, q),
\]

여기서 \(B\)는 압축 표현에 허용된 최대 토큰 예산이다. ISM의 압축 표현은 심볼 집합 \(S\), 사전 \(D\), 심볼 간 관계 \(G\)로 구성된다.

\[
z_{\mathrm{ISM}} = (S, D, G),
\]

\[
S = \{Z_1, \ldots, Z_k\}, \qquad D: Z_i \mapsto c_i.
\]

\(c_i\)는 문서에서 추출된 조건, 사건, 예외 또는 관계를 나타내는 짧은 텍스트 정의다. \(G\)는 심볼의 적용 순서, 함의, 예외 관계 또는 최종 결론을 표현한다.

### 3.2 표현 형식

ISM은 다음 두 형식을 사용한다.

**Symbol + Dictionary**

```text
Z1: marker_a high & marker_b low -> risk+
Z2: missense in domain_2 -> escalate one level
Z3: repair_score > 0.8 -> cancel one escalation
Apply: Z1, then Z2, unless Z3.
```

**Symbol Only**

```text
Z1 Z2 !Z3 => HIGH
```

Symbol + Dictionary 조건은 전체 압축 표현을 사용한다. Symbol Only 조건은 동일하게 생성된 심볼 관계 \(G\)를 유지하되 사전 \(D\)를 제거한다. 따라서 이 조건은 심볼 문자열과 관계 구조만으로 보존되는 정보의 양을 측정한다.

### 3.3 압축 절차

메인 설정에서 압축기와 추론기는 모두 고정된 instruction-tuned LLM이다. 압축 프롬프트는 다음 제약을 부여한다.

1. 출력은 심볼, 짧은 사전, 심볼 간 관계만 포함한다.
2. 원문의 조건, 예외, 우선순위, 임계값 및 시간 관계를 보존한다.
3. 특정 질문의 답을 직접 기록하지 않고, 같은 문서의 여러 질문에 재사용 가능한 표현을 생성한다.
4. tokenizer로 측정한 전체 출력 길이는 \(B\)를 초과하지 않는다.
5. 예산을 넘긴 출력은 임의 절단하지 않고 동일 프롬프트로 다시 생성한다.

압축은 문서마다 한 번 수행하며, 생성된 \(z_{\mathrm{ISM}}\)을 모든 후속 질문에 재사용한다.

### 3.4 개입 연산

ISM의 핵심 특성은 사전과 심볼 라벨에 명시적으로 개입할 수 있다는 점이다. 문서 \(x\)에서 생성한 정상 표현을 \(z=(S,D,G)\)라 할 때 다음 연산을 정의한다.

**Dictionary removal**

\[
\mathcal{I}_{\mathrm{remove}}(z) = (S, \varnothing, G).
\]

**Dictionary corruption**

\[
\mathcal{I}_{\mathrm{corrupt}}(z) = (S, \pi(D), G),
\]

여기서 \(\pi\)는 한 문서 안의 사전 정의를 무작위로 치환하는 derangement이며, 원래 매핑과 동일한 항목을 허용하지 않는다.

**Random-symbol control**

\[
\mathcal{I}_{\mathrm{random}}(z) = (S_{\mathrm{rand}}, \varnothing, G_{\mathrm{rand}}),
\]

여기서 심볼 수와 토큰 길이는 정상 표현과 일치시키지만 의미 있는 매핑과 관계는 제거한다.

**Label swap**

\[
\mathcal{I}_{\mathrm{swap}}(z;\rho) = (\rho(S), D \circ \rho^{-1}, \rho(G)),
\]

여기서 \(\rho\)는 학습 중 사용되지 않은 새로운 라벨 집합으로의 일대일 치환이다. 이 연산은 의미 구조를 유지하면서 표면 라벨만 변경한다.

## 4. 연구 질문

본 연구는 다음 네 가지 연구 질문을 검증한다.

**RQ1.** 심볼과 사전은 장문 추론에 실제로 사용되는가?

- 정상 사전을 제거하거나 오염했을 때 정확도가 하락하는지 측정한다.
- Symbol Only가 길이를 맞춘 Random Symbol보다 높은지 평가한다.

**RQ2.** ISM은 특정 표면 라벨의 암기를 넘어 새로운 라벨-의미 결합을 사용할 수 있는가?

- 학습에서 보지 못한 심볼 라벨로 교환한 뒤 사전 유무에 따른 성능을 비교한다.

**RQ3.** ISM은 동일 토큰 예산에서 기존 압축 방식보다 과제 관련 정보를 더 잘 보존하는가?

- 64, 128, 256, 512 토큰 예산에서 자연어 요약, 키워드 추출, LLMLingua-2와 비교한다.

**RQ4.** 문서 압축을 여러 질문에 재사용할 때 ISM의 비용과 정확도는 어떻게 변하는가?

- Synthetic Rule-QA에서 질문 수가 증가함에 따른 누적 토큰과 정확도 보존율을 측정한다.

## 5. 실험 설정

### 5.1 데이터셋

#### Synthetic Rule-QA

Synthetic Rule-QA는 조건 규칙과 사례 사실을 포함하는 장문 문서, 문서별 복수 질문, 정답, 그리고 정답 생성에 사용된 gold rule graph로 구성한다. Gold graph는 압축 결과의 오류 원인을 추적하고 oracle summary를 생성하는 데 사용한다.

| 항목 | 설정 |
|---|---:|
| Train / Dev / Test | 50,000 / 5,000 / 10,000 documents |
| 문서 길이 | 700–2,000 tokens |
| 문서당 규칙 | 8–20 |
| 문서당 기본 질문 | 3–8 |
| Reuse용 질문 | 50–100 |
| 규칙 유형 | conjunction, disjunction, exception, precedence, threshold, temporal |
| OOD 분할 | template, vocabulary, length, paraphrase |

데이터 생성기는 규칙 그래프를 먼저 표본화한 뒤 이를 자연어 문서로 렌더링한다. 패러프레이즈 분할은 문장을 변환한 후 규칙 그래프를 재추출하여 원본 그래프와 논리적으로 동치인 사례만 포함한다. 특히 conjunction/disjunction, 부정, 예외 범위 및 시간 순서가 바뀐 사례는 제거한다.

#### QASPER

QASPER는 학술 논문 본문을 근거로 질문에 답하는 장문 질의응답 데이터셋이다. 본 연구에서는 synthetic 환경 밖에서 ISM의 정보 보존 성능을 검증하는 외적 타당도 데이터로 사용한다. QASPER의 문서당 질문 수는 reuse 분석에 충분하지 않으므로 RQ4의 근거로 사용하지 않는다.

### 5.2 모델

주 추론기 \(R\)과 기본 압축기 \(C\)는 4-bit Qwen2.5-7B-Instruct를 사용한다. 압축기 크기에 대한 민감도 분석에서는 Qwen2.5-1.5B-Instruct를 추가한다. QASPER에서는 Full Context 성능이 지나치게 낮은 모델의 Accuracy Retention이 의미를 잃을 수 있으므로 1.5B 모델을 메인 추론기로 사용하지 않는다.

Dictionary Swap 실험에서는 Qwen2.5-1.5B-Instruct 또는 SmolLM2-1.7B-Instruct에 LoRA를 적용한다. 이 학습은 전체 QA 능력을 새로 학습하기 위한 것이 아니라, 심볼 라벨과 개념 정의를 분리하고 사전 기반 결합을 유도하기 위한 통제된 학습으로 제한한다.

모든 조건에서 temperature는 0으로 고정하고, 모델 revision, tokenizer, quantization, 최대 입력 길이 및 decoding parameter를 공개한다.

### 5.3 비교 방법

| 방법 | 설명 |
|---|---|
| Full Context | 원문 전체를 사용하는 비압축 상한 |
| Oracle Gold Summary | gold graph에서 질문 관련 규칙을 자연어로 렌더링한 오라클 |
| Model Summary | 동일 압축기가 생성한 일반 자연어 요약 |
| Keyword Extract | TF-IDF, YAKE 또는 TextRank 기반 추출 |
| LLMLingua-2 | 학습 기반 task-agnostic prompt compression |
| ISM | 제안한 Symbol + Dictionary 압축 |

Oracle Gold Summary는 실제 사용 가능한 기준선이 아니라 정보 보존의 상한 참조다. Model Summary와 반드시 분리해 보고하며, ISM이 Oracle Gold Summary를 유의하게 능가할 경우 데이터 누수나 평가 구현 오류를 우선 점검한다.

### 5.4 토큰 예산의 정렬

Fixed-Budget 실험에서는 \(B \in \{64,128,256,512\}\)를 사용한다. 각 방법의 압축 결과와 공통 지시문을 동일 tokenizer로 측정한다. 질문과 답변 생성용 공통 프롬프트는 예산에서 제외하되 모든 조건에서 동일하게 유지한다. 방법별로 달라지는 문서 표현만 \(B\) 이하로 제한한다.

ISM에서는 심볼 사전과 관계 표현을 모두 예산에 포함한다. 예산 초과 출력을 사후 절단하면 방법별 정보 손실 방식이 달라지므로, 제약을 만족할 때까지 재생성한다. 재생성 횟수와 실패율을 함께 보고한다.

## 6. 실험

### 6.1 Dictionary Ablation

RQ1을 위해 다음 조건을 동일 문서-질문 쌍에서 비교한다.

| 조건 | 심볼 | 사전 | 관계 | 목적 |
|---|---|---|---|---|
| Full Symbol + Dict | 정상 | 정상 | 정상 | ISM 전체 성능 |
| Symbol Only | 정상 | 제거 | 정상 | 사전 없이 보존되는 정보 |
| Corrupted Dict | 정상 | 잘못된 치환 | 정상 | 의미 매핑 의존도 |
| Random Symbol | 무작위 | 없음 | 길이 일치 무작위 | 노이즈 하한 |

사전이 기능적으로 사용된다면 Full Symbol + Dict는 Corrupted Dict보다 높아야 한다. 심볼 관계 자체에 정보가 있다면 Symbol Only는 Random Symbol보다 높아야 한다. 사전 오염은 단순 정보 제거와 달리 잘못된 정보를 제공하므로, Corrupted Dict가 Random Symbol보다 더 낮아질 가능성도 별도로 분석한다.

동일 토큰 예산의 Model Summary를 추가하여 ISM이 자연어 요약의 표기 변형인지 평가한다. 핵심 비교는 다음과 같다.

\[
\Delta_{\mathrm{map}}
= Acc_{\mathrm{Full+Dict}}-Acc_{\mathrm{Corrupt}},
\]

\[
\Delta_{\mathrm{symbol}}
= Acc_{\mathrm{SymbolOnly}}-Acc_{\mathrm{Random}}.
\]

### 6.2 Dictionary Swap

RQ2는 라벨 종류와 사전 유무를 교차한 \(2 \times 2\) 설계로 평가한다.

| 라벨 조건 | 사전 있음 | 사전 없음 |
|---|---|---|
| Original labels | 원래 라벨과 정상 사전 | 원래 라벨만 제공 |
| Unseen swapped labels | 미관측 라벨과 교환된 사전 | 미관측 라벨만 제공 |

학습에는 `Z` 계열 라벨만 사용하고, 평가에는 학습 중 한 번도 등장하지 않은 `Q` 계열 또는 별도 심볼 집합을 사용한다. 주 비교는 Original + Dictionary와 Unseen Swap + Dictionary 사이의 정확도 차이다. 두 조건의 성능이 유사하면 모델이 특정 문자열의 암기보다 주어진 사전과 구조를 사용할 가능성을 지지한다.

사전이 없는 Unseen Swap은 가장 강한 조건이지만, 임의 라벨에 고유 의미가 없으므로 높은 절대 성능을 필수 성공 조건으로 두지 않는다. 이 조건은 사전 없이도 관계 구조만 전이되는 범위를 진단하는 보조 분석으로 사용한다.

### 6.3 Fixed-Budget Comparison

RQ3에서는 각 토큰 예산에서 Full Context, 두 종류의 summary, Keyword Extract, LLMLingua-2, ISM을 비교한다. 주 결과는 Accuracy Retention과 Efficiency Score이며, 예산별 정확도-압축률 프런티어를 함께 제시한다.

ISM의 성공을 LLMLingua-2에 대한 전 예산 우위로만 정의하지 않는다. ISM이 비슷한 Accuracy Retention을 보이면서 Dictionary Ablation과 Swap에서 개입 가능성을 입증한다면 서로 다른 장점을 갖는 방법으로 해석한다.

### 6.4 Reuse

RQ4는 Synthetic Rule-QA의 reuse 전용 split에서 평가한다. 각 문서에 대해 Full Context는 질문마다 원문을 다시 입력하고, Model Summary와 ISM은 문서당 한 번 생성한 표현을 캐시한다.

질문 \(n\)개에 대한 총 입력 토큰 비용을 다음과 같이 계산한다.

\[
T_{\mathrm{full}}(n)=n(|x|+|q|),
\]

\[
T_{\mathrm{cache}}(n)=|x|+|z|+n(|z|+|q|),
\]

여기서 첫 번째 \(|x|\)는 압축 생성 비용을 포함한다. 생성 비용을 제외한 serving-only 비용도 별도로 보고한다.

캐시는 summary에도 동일하게 적용할 수 있으므로, 비용 절감 자체를 ISM만의 기여로 주장하지 않는다. 동일 예산에서 질문 수와 질문 유형이 늘어날 때 ISM과 Model Summary의 Accuracy Retention이 어떻게 달라지는지를 주로 분석한다.

## 7. 평가 지표와 통계 분석

### 7.1 평가 지표

압축 조건 \(m\)에 대한 Accuracy Retention은 다음과 같다.

\[
AR_m = \frac{Acc_m}{Acc_{\mathrm{full}}}.
\]

Compression Ratio는 문서 표현의 실제 토큰 수로 계산한다.

\[
CR_m = \frac{Tokens_m}{Tokens_{\mathrm{full}}}.
\]

Efficiency Score는 단위 압축률당 정확도 보존율이다.

\[
ES_m = \frac{AR_m}{CR_m}.
\]

Dictionary Swap의 강건성은 다음과 같다.

\[
SR =
\frac{Acc_{\mathrm{UnseenSwap+Dict}}}
{Acc_{\mathrm{Original+Dict}}}.
\]

Ablation 결과는 \(\Delta_{\mathrm{map}}\), \(\Delta_{\mathrm{symbol}}\), 그리고 각 조건의 paired accuracy difference로 보고한다.

### 7.2 보조 분석

Synthetic Rule-QA에서는 gold graph를 사용해 다음을 추가 분석한다.

- 생성된 심볼과 gold rule 사이의 purity
- 규칙 유형별 누락 및 오표현 비율
- 예외와 우선순위 규칙의 오류율
- template, vocabulary, length, paraphrase OOD별 AR
- 토큰 예산별 심볼 수, 사전 길이 및 관계 표현 길이

### 7.3 통계 검정

모든 방법은 동일한 문서-질문 쌍에서 평가한다. 정확도 차이는 McNemar 검정을 사용하고, AR, ES, SR 및 paired difference의 95% 신뢰구간은 10,000회 paired bootstrap으로 계산한다. 토큰 수와 지연 시간은 Wilcoxon signed-rank 검정으로 비교한다. 여러 토큰 예산과 조건에 대한 검정에는 Holm-Bonferroni 보정을 적용한다.

통계적 유의성만으로 결론을 내리지 않고 효과 크기와 신뢰구간을 우선 보고한다. Full Context 정확도가 사전에 정한 최소 기준보다 낮은 모델-데이터 조합은 AR의 주 분석에서 제외하고 별도 sanity result로 제시한다.

## 8. 결과

> 이 절은 실험 완료 후 채운다. 아래 표와 문장 틀은 결과를 과장하거나 선택적으로 보고하지 않기 위한 사전 형식이다.

### 8.1 Dictionary Ablation

| 조건 | Accuracy | AR | Full+Dict 대비 차이 | 95% CI |
|---|---:|---:|---:|---:|
| Full Context | [ ] | 1.000 | - | [ ] |
| Full Symbol + Dict | [ ] | [ ] | - | [ ] |
| Symbol Only | [ ] | [ ] | [ ] | [ ] |
| Corrupted Dict | [ ] | [ ] | [ ] | [ ] |
| Random Symbol | [ ] | [ ] | [ ] | [ ] |
| Model Summary | [ ] | [ ] | [ ] | [ ] |

보고 문장:

> Full Symbol + Dict의 정확도는 [값]이었으며, 사전 오염 후 [값]으로 [하락/유지]하였다(\(\Delta_{\mathrm{map}}=[값]\), 95% CI [구간]). Symbol Only는 Random Symbol보다 [값]%p [높았다/차이가 없었다](95% CI [구간]). 이 결과는 [사전 매핑과 심볼 구조가 모두 기능적으로 사용됨 / 사전만 사용됨 / 유효한 심볼 정보를 확인하지 못함]을 시사한다.

### 8.2 Dictionary Swap

| 라벨 | 사전 | Accuracy | SR | 95% CI |
|---|---|---:|---:|---:|
| Original | 있음 | [ ] | 1.000 | [ ] |
| Original | 없음 | [ ] | [ ] | [ ] |
| Unseen Swap | 있음 | [ ] | [ ] | [ ] |
| Unseen Swap | 없음 | [ ] | [ ] | [ ] |

보고 문장:

> 미관측 라벨과 교환된 사전을 제공했을 때 정확도는 [값]으로, 원래 라벨 조건 대비 [값]의 성능을 유지했다(\(SR=[값]\), 95% CI [구간]). 이는 [사전 기반 binding을 지지함 / 표면 라벨 암기 가설을 배제하기 어려움]을 나타낸다.

### 8.3 Fixed-Budget Comparison

| 방법 | 64 | 128 | 256 | 512 |
|---|---:|---:|---:|---:|
| Oracle Gold Summary | [ ] | [ ] | [ ] | [ ] |
| Model Summary | [ ] | [ ] | [ ] | [ ] |
| Keyword Extract | [ ] | [ ] | [ ] | [ ] |
| LLMLingua-2 | [ ] | [ ] | [ ] | [ ] |
| ISM | [ ] | [ ] | [ ] | [ ] |

각 셀에는 `AR / ES`를 기록하고, 원시 정확도와 95% CI는 부록 표에 제시한다.

### 8.4 Reuse 및 QASPER

| 데이터 | 방법 | 질문 수 | 총 토큰 | 질문당 토큰 | Accuracy | AR |
|---|---|---:|---:|---:|---:|---:|
| Synthetic | Full Context | [ ] | [ ] | [ ] | [ ] | 1.000 |
| Synthetic | Model Summary | [ ] | [ ] | [ ] | [ ] | [ ] |
| Synthetic | ISM | [ ] | [ ] | [ ] | [ ] | [ ] |
| QASPER | Full Context | - | [ ] | [ ] | [ ] | 1.000 |
| QASPER | LLMLingua-2 | - | [ ] | [ ] | [ ] | [ ] |
| QASPER | ISM | - | [ ] | [ ] | [ ] | [ ] |

QASPER 결과는 실제 자연어에서의 정보 보존 가능성만 뒷받침하며, reuse에 대한 근거로 해석하지 않는다.

## 9. 논의

### 9.1 압축 효율과 개입 가능성

ISM은 압축률 하나로 평가하기보다 성능과 개입 결과를 함께 해석해야 한다. Full Symbol + Dict가 강한 성능을 보이고 Corrupted Dict에서 유의한 하락이 나타난다면 모델이 명시적 의미 매핑을 사용한다는 근거가 된다. Symbol Only가 Random Symbol보다 높다면 사전을 제외한 심볼 관계에도 과제 관련 정보가 남아 있음을 의미한다.

반면 Full Symbol + Dict만 높고 Symbol Only가 Random과 구분되지 않는다면, ISM의 효용은 독립적인 심볼 체계보다 구조화된 초단문 요약에 가깝다. 이 경우에도 사전 오염에 대한 민감도는 검사 가능한 압축 형식의 장점으로 남지만, 심볼 자체가 정보를 담는다는 주장은 축소해야 한다.

### 9.2 라벨 교환의 해석

Unseen Swap + Dictionary에서 성능이 유지되면 특정 `Z` 문자열에 대한 암기만으로 결과를 설명하기 어렵다. 다만 이는 모델 내부에 고정된 인간 유사 개념이 존재한다는 증거가 아니라, 입력으로 제공된 사전과 관계를 사용해 새로운 표면 라벨을 재결합할 수 있다는 증거다.

Unseen Swap + No Dictionary는 임의 라벨의 의미를 복원할 단서가 제한된 조건이다. 따라서 이 조건의 실패는 binding 가설을 직접 반박하지 않는다. 핵심은 교환된 사전을 제공했을 때 원래 표현의 기능이 얼마나 회복되는가이다.

### 9.3 자연어 요약과의 관계

ISM은 텍스트로 표현되므로 자연어 요약과 완전히 분리된 범주가 아니다. Fixed-Budget 실험에서 Model Summary보다 우수하지 않고 ablation에서도 심볼 구조의 독립적 효과가 없다면, ISM은 자연어 요약의 표기 변형으로 보는 것이 타당하다. 반대로 동일 예산에서 높은 AR 또는 ES를 보이고 사전 개입에 체계적으로 반응한다면, ISM은 정보 밀도와 검사 가능성을 결합한 구조화 압축으로 평가할 수 있다.

### 9.4 실패 결과의 가치

본 연구는 양의 결과만을 전제로 하지 않는다. Symbol Only가 Random과 다르지 않거나, 사전 교환 후 성능이 회복되지 않거나, 자연어 요약이 모든 예산에서 우세할 수 있다. 이러한 결과는 prompt-only 이산 심볼 압축의 한계를 규명하고, 어떤 수준의 학습 또는 잔여 메모리가 필요한지 보여준다.

## 10. 한계

첫째, Synthetic Rule-QA의 규칙 구조는 실제 문서보다 명확하고 폐쇄적이다. QASPER를 통해 외적 타당도를 보완하지만, 두 데이터셋만으로 모든 장문 추론 과제에 일반화할 수 없다.

둘째, 텍스트 심볼과 사전은 사람이 검사할 수 있지만 자동으로 해석 가능하거나 충실하다고 보장되지 않는다. 심볼 정의가 원문의 인과 구조를 정확히 반영하는지는 gold graph가 없는 실제 문서에서 완전히 검증하기 어렵다.

셋째, Dictionary Swap에는 소규모 LoRA 학습이 사용되므로 prompt-only 메인 실험과 학습 조건이 다르다. Swap 결과는 학습 없는 일반 능력이 아니라, 제한된 binding 학습 이후의 전이 능력으로 해석해야 한다.

넷째, Efficiency Score는 간결하지만 정확도 보존율을 압축률로 나눈 비율 지표이므로 매우 작은 CR에서 과도하게 커질 수 있다. 따라서 AR-CR 프런티어와 원시 정확도를 항상 함께 보고한다.

다섯째, 실제 시스템 비용은 토큰 수 외에도 압축 생성 비용, KV-cache, 하드웨어, 배치 크기 및 지연 시간의 영향을 받는다. Reuse 실험에서는 압축 생성 비용을 포함한 end-to-end 비용과 serving-only 비용을 분리한다.

## 11. 결론

본 논문은 장문 문서를 재사용 가능한 이산 텍스트 심볼과 사전으로 압축하는 Inspectable Symbolic Compression을 제안한다. ISM의 핵심은 단순히 입력을 줄이는 데 있지 않다. 정상 사전을 제거하거나 오염시키고, 심볼 라벨을 미관측 집합으로 교환함으로써 압축 표현이 실제로 어떤 정보에 의존하는지 시험할 수 있다.

Synthetic Rule-QA에서는 이러한 개입의 원인을 gold rule graph와 함께 분석하고, QASPER에서는 실제 학술 문서에서의 정보 보존 성능을 검증한다. 동일 토큰 예산의 자연어 요약과 LLMLingua-2를 비교하여 효율성을 평가하되, ISM의 주된 차별점은 경쟁적인 압축 성능과 명시적 개입 가능성의 결합으로 정의한다. 실험 결과가 이 가설을 지지하지 않는 경우에도, 본 프로토콜은 이산 심볼 압축이 구조화 요약과 구분되는 조건과 한계를 명확히 드러낼 수 있다.

## 윤리적 고려

본 연구는 공개 또는 합성 텍스트를 사용하며 사람을 대상으로 한 의사결정 시스템을 구축하지 않는다. 그럼에도 압축 표현이 원문 정보를 누락하거나 왜곡할 수 있으므로, 실제 고위험 응용에서 ISM을 원문 검토의 대체물로 사용해서는 안 된다. 생성 데이터, 프롬프트, 모델 버전, 실패 사례 및 통계 코드를 공개하여 결과의 재현성과 검증 가능성을 확보한다.

## 재현성 진술

최종 논문과 함께 다음 자료를 공개한다.

- Synthetic Rule-QA 생성 코드, gold rule graph 및 데이터 split
- 압축기와 추론기에 사용한 전체 프롬프트
- 모델 이름, revision, tokenizer 및 quantization 설정
- 토큰 예산 검증과 재생성 절차
- LoRA hyperparameter와 학습 로그
- paired evaluation, bootstrap 및 통계 검정 코드
- 생성된 심볼·사전 cache와 실패 사례

## 참고문헌

[1] Koh, P. W. et al. “Concept Bottleneck Models.” ICML, 2020.

[2] Espinosa Zarlenga, M. et al. “Concept Embedding Models: Beyond the Accuracy-Explainability Trade-Off.” NeurIPS, 2022.

[3] Ismail, A. A. et al. “Concept Bottleneck Generative Models.” ICLR, 2024.

[4] Tan, A. et al. “Concept Bottleneck Model with Open Vocabulary Concepts.” ECCV, 2024.

[5] Rao, S. et al. “Discover-then-Name: Task-Agnostic Concept Bottlenecks via Automated Concept Discovery.” ECCV, 2024.

[6] Sun, C.-E. et al. “Concept Bottleneck Large Language Models.” 2024.

[7] Jiang, H. et al. “LLMLingua: Compressing Prompts for Accelerated Inference of Large Language Models.” EMNLP, 2023.

[8] Jiang, H. et al. “LongLLMLingua: Accelerating and Enhancing LLMs in Long Context Scenarios via Prompt Compression.” ACL, 2024.

[9] Pan, Z. et al. “LLMLingua-2: Data Distillation for Efficient and Faithful Task-Agnostic Prompt Compression.” Findings of ACL, 2024.

[10] Li, Y. et al. “Compressing Context to Enhance Inference Efficiency of Large Language Models.” EMNLP, 2023.

[11] Mu, J., Li, X. L., and Goodman, N. “Learning to Compress Prompts with Gist Tokens.” NeurIPS, 2023.

[12] Chevalier, A. et al. “Adapting Language Models to Compress Long Contexts.” EMNLP, 2023.

[13] Ge, T. et al. “In-context Autoencoder for Context Compression in a Large Language Model.” ICLR, 2024.

[14] Dai, Y. et al. “Pretraining Context Compressor for Large Language Models with Embedding-Based Memory.” ACL, 2025.

[15] Cheng, X. et al. “xRAG: Extreme Context Compression for Retrieval-Augmented Generation with One Token.” NeurIPS, 2024.

## 부록 A. 사전등록된 판정 기준

주 가설을 지지하기 위한 최소 조건은 다음과 같다.

1. ISM이 Model Summary보다 유의하게 높은 AR 또는 ES를 보인다.
2. Symbol Only가 Random Symbol보다 높고, Full Symbol + Dict가 Corrupted Dict보다 높다.
3. Unseen Swap + Dictionary가 Original + Dictionary 성능의 대부분을 유지한다.

정확한 실질적 동등성 또는 최소 효과 크기 경계는 dev set 결과를 보기 전에 확정한다. 세 조건 중 첫 번째가 실패하면 ISM의 효율 우위를 주장하지 않는다. 두 번째가 실패하면 심볼이 기능적 정보를 담는다는 주장을 하지 않는다. 세 번째가 실패하면 라벨-개념 binding의 전이 가능성을 주장하지 않는다.

## 부록 B. 후속 연구

본 논문의 범위에서 제외한 후속 방향은 Symbol + Residual Memory, adaptive symbolization, continuous-discrete hybrid compression, embedding slot, RAG 및 멀티턴 대화 적용이다.
