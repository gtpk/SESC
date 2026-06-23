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

QASPER 답변은 extractive, abstractive, yes/no, unanswerable 네 유형이 혼재하므로 단순 exact-match accuracy 대신 QASPER 표준인 **token 단위 answer-F1**(Dasigi et al., 2021)로 채점한다. 정규화는 소문자화·구두점 제거·관사 제거·공백 정규화를 적용하고, 질문마다 복수 주석자 정답에 대한 **최대 F1**을 취한다. unanswerable 정답은 예측이 무답(빈 문자열 또는 "unanswerable")일 때만 정답으로 처리하며, 결과는 answer type별로 분해하여 보고한다. Synthetic Rule-QA는 폐쇄형 단일 라벨이므로 exact-match로 채점한다. 두 데이터셋의 채점 차이는 §7.1에 명시한다.

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

정확도(\(Acc\))의 정의는 데이터셋에 따라 다르다. Synthetic Rule-QA는 폐쇄형 단일 라벨이므로 정규화 후 exact-match 비율을 사용한다. QASPER는 §5.1에 정의한 token 단위 answer-F1의 평균을 사용하며, 이때 \(Acc\)는 평균 answer-F1을 의미한다. 두 경우 모두 Accuracy Retention은 동일한 형태로 정의한다.

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

#### 8.1.1 예비 결과 (dev pilot — 등록 규모 아님)

> **주의:** dev 파일럿(N=40), 등록 규모 아님. Qwen2.5-7B-Instruct 4-bit(압축기=추론기),
> greedy, 단일 seed. 비교군 Model Summary는 미구현으로 제외. RQ1 **결론**이 아니라 예비 신호다.
> 진단 경과는 [docs/reviews/llm-ism-diagnostic.md](../docs/reviews/llm-ism-diagnostic.md).

이 절은 두 개의 개입 강도를 구분한다. **derangement**(사전 정의를 라벨 간 순열; 정의 집합은
보존)는 *라벨-바인딩* 민감도를 측정하고, **conclusion flip**(결론 HIGH↔LOW, True↔False 반전;
조건은 유지)은 *사전 의미내용* 민감도를 측정한다. 초기 파일럿에서 관찰된 \(\Delta_{\mathrm{map}}\approx0\)은
(1) 압축기가 결론을 누락한 낮은 purity와 (2) 내용을 보존하는 derangement의 산물이었다(진단 참조).
아래는 압축기 purity를 1.0으로 끌어올리고(결론 포함 강제) 내용 변경형 corruption을 추가한 뒤의
결과다. 증거: [docs/evidence/ablation-qwen7b-strong/](../docs/evidence/ablation-qwen7b-strong/README.md),
config_hash `15c72cfd…`, commit `7be5618`, 압축 20/20.

| 조건 | Accuracy | AR | CR |
|---|---:|---:|---:|
| Full Context | 0.700 | 1.000 | 1.000 |
| Full Symbol + Dict | 0.500 | 0.714 | 0.730 |
| Corrupted Dict (derangement) | 0.450 | 0.643 | 0.730 |
| Flipped Dict (conclusion flip) | 0.325 | 0.464 | 0.730 |
| Blank Dict | 0.225 | 0.321 | 0.206 |
| Symbol Only | 0.450 | 0.643 | 0.070 |
| Random Symbol | 0.250 | 0.357 | 0.722 |

- \(\Delta_{\mathrm{map}}^{\mathrm{derange}}\) (label-binding, 보조) = Acc(Full+Dict) − Acc(Deranged) = **+0.050**, 95% CI [−0.175, 0.275], McNemar p=0.83 (n=40)
- \(\Delta_{\mathrm{map}}^{\mathrm{flip}}\) (semantic-content, **primary**) = Acc(Full+Dict) − Acc(Flipped) = **+0.175**, 95% CI [0.000, 0.350], McNemar p=0.12 (n=40)
- \(\Delta_{\mathrm{symbol}}\) (symbolic-structure) = Acc(SymbolOnly) − Acc(Random) = **+0.200**, 95% CI [0.075, 0.350], McNemar p=0.021 (n=40)

(이름 정의는 [부록 A.1](#a1-amendment--corruption-contrast의-construct-validity-dev-pilot-진단-후). 증거 JSON
`ablation-qwen7b-strong`은 rename 이전 키 `delta_map`/`delta_map_strong`을 사용한다.)

예비 보고:

> 사전 정의를 라벨 간 순열한 derangement는 정확도를 떨어뜨리지 않았다
> (\(\Delta_{\mathrm{map}}=+0.05\), CI가 0 포함). 그러나 사전의 **결론을 반전**하면 정확도가
> 0.500→0.325로 하락했고(\(\Delta_{\mathrm{map}}^{\mathrm{strong}}=+0.175\), CI [0, 0.35]),
> Symbol Only(0.450)는 Random Symbol(0.250)을 유의하게 능가했다
> (\(\Delta_{\mathrm{symbol}}=+0.20\), McNemar p=0.021). 이는 이 규모에서 **심볼 구조와 사전
> 의미내용이 모두 추론에 사용된다**는 예비 증거다(라벨 자체의 바인딩은 사용되지 않음). 부록 A
> 기준 #2의 "Symbol Only > Random"은 충족, "Full+Dict > Corrupt"는 derangement가 아니라
> **내용 변경형 corruption(Flipped)** 으로 평가해야 함을 시사한다.

판정 한계: \(\Delta_{\mathrm{map}}^{\mathrm{strong}}\)은 N=40에서 경계적(p=0.12)이므로 RQ1 확정은
**등록 규모(dev 5k) paired evaluation** 후로 미룬다. blank_dict(0.225)≈Random(0.25)은 정의 내용
제거가 거의 무작위 수준으로 떨어짐을 보인다.

#### 8.1.2 Dev scale-up 결과 (N=120 문서 / 240 문항)

> dev pilot(8.1.1, N=40)을 확장한 결과다. **full registered scale(dev 5k)은 아니며**, 압축
> batching 등 추가 컴퓨트 후 확정한다. 단 부록 A.1의 construct-valid contrast가 이 규모에서
> 유의해졌다. 증거: [docs/evidence/ablation-qwen7b-N120/](../docs/evidence/ablation-qwen7b-N120/README.md),
> config_hash `c907f84…`, commit `87e216e`, 압축 120/120(실패 0), 3×40 샤드 + resume/merge.
> 비교군 Model Summary는 미구현으로 제외.

| 조건 | Accuracy | AR | CR |
|---|---:|---:|---:|
| Full Context | 0.750 | 1.000 | 1.000 |
| Full Symbol + Dict | 0.446 | 0.594 | 0.745 |
| Corrupted Dict (derange) | 0.375 | 0.500 | 0.745 |
| Flipped Dict (flip) | 0.367 | 0.489 | 0.745 |
| Blank Dict | 0.250 | 0.333 | 0.215 |
| Symbol Only | 0.413 | 0.550 | 0.079 |
| Random Symbol | 0.304 | 0.406 | 0.738 |

- \(\Delta_{\mathrm{map}}^{\mathrm{derange}}\) (label-binding, 보조) = **+0.071**, 95% CI [−0.021, 0.163], McNemar p=0.159 (n=240)
- \(\Delta_{\mathrm{map}}^{\mathrm{flip}}\) (semantic-content, **primary**) = **+0.079**, 95% CI [0.013, 0.146], McNemar **p=0.032** (n=240)
- \(\Delta_{\mathrm{symbol}}\) (symbolic-structure) = **+0.108**, 95% CI [0.050, 0.167], McNemar **p=0.0005** (n=240)

보고 문장:

> dev scale-up(N=240)에서 사전의 **결론을 반전**하면 정확도가 0.446→0.367로 하락했고
> (\(\Delta_{\mathrm{map}}^{\mathrm{flip}}=+0.079\), 95% CI [0.013, 0.146], p=0.032),
> Symbol Only(0.413)는 Random Symbol(0.304)을 능가했다(\(\Delta_{\mathrm{symbol}}=+0.108\), p=0.0005).
> 반면 라벨 순열(derangement)은 유의한 영향이 없었다(\(\Delta_{\mathrm{map}}^{\mathrm{derange}}=+0.071\),
> CI가 0 포함, p=0.16). 이는 **심볼 구조와 사전 의미내용이 모두 추론에 사용되며 라벨 자체의
> 바인딩은 사용되지 않음**을 시사한다. 부록 A.1의 amended primary 기준(Full+Dict > Flipped
> AND Symbol Only > Random)을 dev scale-up에서 충족한다. 최종 확정은 full registered scale
> 에서 수행한다.

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

#### 8.3.1 예비 결과 (long-context smoke — N=10 문서)

> **주의:** 파이프라인·budget fairness 검증용 smoke다(N=10 문서 / 20 문항, 단일 seed,
> 통계 아님). 문서는 long-context 프로파일(700–2000 토큰, full_context 평균 1262)로,
> 예산 64–512가 실제 압축이 되도록 했다. LLMLingua-2는 미구현으로 제외. 증거:
> [docs/evidence/fixed-budget-long-smoke/](../docs/evidence/fixed-budget-long-smoke/README.md),
> config `fixed_budget_qwen7b_long`, commit `714eff1`. 셀 값은 `AR / ES`.

| 방법 | 64 | 128 | 256 | 512 |
|---|---:|---:|---:|---:|
| Oracle Gold Summary | 0.86 / 18.3 | 0.86 / 12.3 | 0.86 / 12.3 | 0.86 / 12.3 |
| Model Summary | **1.29 / 76.9** | 1.21 / 63.3 | **1.36 / 19.9** | 1.21 / 13.3 |
| Keyword Extract | 0.86 / 16.9 | 0.79 / 7.7 | 0.79 / 4.3 | 0.86 / 4.1 |
| LLMLingua-2 | — | — | — | — |
| ISM | (floor 실패) | 0.86 / 11.2 | 0.86 / 11.0 | 0.86 / 10.8 |

Full Context 기준: Accuracy 0.70 (AR 1.000, CR 1.000). ISM은 표현 floor(~100 whitespace 토큰)로
budget 64를 충족하지 못해 미생성(stress point).

예비 보고:

> 이 smoke에서 Model Summary는 모든 예산에서 ISM보다 높은 AR과 ES를 보였고, 다수 셀에서
> AR > 1(Full Context 초과)이었다. 이는 1262토큰 문서의 상당 부분이 중립 filler이기 때문으로,
> 요약이 과제 관련 규칙만 추출해 노이즈를 제거한 효과로 보인다. ISM은 AR 0.86 / ES ~11로
> keyword·oracle 수준이며 summary보다 낮았다. 따라서 부록 A 기준 #1(ISM > Model Summary)은
> 이 규모에서 충족되지 않을 가능성이 크다. 6.1에서 ISM의 심볼 구조·사전 내용 사용이 입증된
> 점과 종합하면, ISM의 차별점은 **토큰 효율이 아니라 검사·개입 가능성**으로 해석하는 것이
> 타당하다(§9.3). 통계 확정은 더 큰 N에서 수행한다.

#### 8.3.2 Dev pilot 결과 (N=40 문서 / 80 문항)

> dev pilot이다. **full registered scale 아님.** long-context(700–2000 tok, full_context 평균 1326),
> 4×10 샤드 + merge. budget 64는 ISM 표현 floor(~100 tok)로 제외하고 primary는 128/256/512.
> 증거: [docs/evidence/fixed-budget-N40/](../docs/evidence/fixed-budget-N40/README.md),
> config `fixed_budget_qwen7b_long`, commit `5d4500d`. 셀 값 `AR / ES`.

| 방법 | 128 | 256 | 512 |
|---|---:|---:|---:|
| Oracle Gold Summary | 0.732 / 11.0 | 0.732 / 11.0 | 0.732 / 11.0 |
| Model Summary | 1.036 / 51.3 | 1.125 / 17.3 | 1.196 / 13.3 |
| Keyword Extract | 0.714 / 7.4 | 0.732 / 4.2 | 0.750 / 3.6 |
| LLMLingua-2 | — | — | — |
| ISM | 0.679 / 9.4 | 0.679 / 9.3 | 0.661 / 8.9 |

Full Context 기준 Accuracy 0.700. AR(vs full_context)은 filler에 의해 오염될 수 있으므로(§9.3.1),
**primary는 같은 문항 paired 비교**다.

**Primary paired contrast — Model Summary vs ISM (same questions, N=80):**

| budget | \(\Delta=Acc_{\mathrm{summary}}-Acc_{\mathrm{ISM}}\) | 95% CI | McNemar p | discordant (S✓I✗ / I✓S✗) |
|---:|---:|---:|---:|---|
| 128 | **+0.250** | [0.100, 0.400] | **0.0029** | 31 / 11 |
| 256 | **+0.3125** | [0.175, 0.450] | **1.1e-4** | 33 / 8 |
| 512 | **+0.375** | [0.250, 0.500] | **2.3e-7** | 33 / 3 |

보고 문장:

> 동일 문항 paired 비교에서 Model Summary는 ISM을 모든 예산에서 유의하게 능가했다(McNemar
> p<0.01, 512에서 p<1e-6; 격차 +0.25→+0.31→+0.375). 두 방법 모두 filler를 제거하므로 이 결과는
> §9.3.1의 filler artifact와 독립적이다. 따라서 부록 A 기준 #1(ISM이 Model Summary 대비 AR/ES
> 우위)은 dev pilot에서 **충족되지 않는다**. ISM의 정확도 보존은 keyword/oracle 수준이었다. full
> registered-scale 확정과 LLMLingua-2 비교는 후속으로 남긴다.

### 8.4 Reuse 및 QASPER

| 데이터 | 방법 | 질문 수 | 총 토큰 | 질문당 토큰 | Accuracy | AR |
|---|---|---:|---:|---:|---:|---:|
| Synthetic | Full Context | [ ] | [ ] | [ ] | [ ] | 1.000 |
| Synthetic | Model Summary | [ ] | [ ] | [ ] | [ ] | [ ] |
| Synthetic | ISM | [ ] | [ ] | [ ] | [ ] | [ ] |
| QASPER | Full Context | - | [ ] | [ ] | [ ] | 1.000 |
| QASPER | LLMLingua-2 | - | [ ] | [ ] | [ ] | [ ] |
| QASPER | ISM | - | [ ] | [ ] | [ ] | [ ] |

QASPER 결과는 실제 자연어에서의 정보 보존 가능성만 뒷받침하며, reuse에 대한 근거로 해석하지 않는다. QASPER의 Accuracy 열은 평균 answer-F1이며, 부록에 answer type별(extractive/abstractive/yes_no/unanswerable) F1 분해를 함께 제시한다.

## 9. 논의

### 9.1 압축 효율과 개입 가능성

ISM은 압축률 하나로 평가하기보다 성능과 개입 결과를 함께 해석해야 한다. Full Symbol + Dict가 강한 성능을 보이고 Corrupted Dict에서 유의한 하락이 나타난다면 모델이 명시적 의미 매핑을 사용한다는 근거가 된다. Symbol Only가 Random Symbol보다 높다면 사전을 제외한 심볼 관계에도 과제 관련 정보가 남아 있음을 의미한다.

반면 Full Symbol + Dict만 높고 Symbol Only가 Random과 구분되지 않는다면, ISM의 효용은 독립적인 심볼 체계보다 구조화된 초단문 요약에 가깝다. 이 경우에도 사전 오염에 대한 민감도는 검사 가능한 압축 형식의 장점으로 남지만, 심볼 자체가 정보를 담는다는 주장은 축소해야 한다.

### 9.2 라벨 교환의 해석

Unseen Swap + Dictionary에서 성능이 유지되면 특정 `Z` 문자열에 대한 암기만으로 결과를 설명하기 어렵다. 다만 이는 모델 내부에 고정된 인간 유사 개념이 존재한다는 증거가 아니라, 입력으로 제공된 사전과 관계를 사용해 새로운 표면 라벨을 재결합할 수 있다는 증거다.

Unseen Swap + No Dictionary는 임의 라벨의 의미를 복원할 단서가 제한된 조건이다. 따라서 이 조건의 실패는 binding 가설을 직접 반박하지 않는다. 핵심은 교환된 사전을 제공했을 때 원래 표현의 기능이 얼마나 회복되는가이다.

### 9.3 자연어 요약과의 관계

ISM은 텍스트로 표현되므로 자연어 요약과 완전히 분리된 범주가 아니다. Fixed-Budget 실험에서 Model Summary보다 우수하지 않고 ablation에서도 심볼 구조의 독립적 효과가 없다면, ISM은 자연어 요약의 표기 변형으로 보는 것이 타당하다. 반대로 동일 예산에서 높은 AR 또는 ES를 보이고 사전 개입에 체계적으로 반응한다면, ISM은 정보 밀도와 검사 가능성을 결합한 구조화 압축으로 평가할 수 있다.

#### 9.3.1 dev smoke의 시사점 (초안)

> dev smoke(§8.3.1, N=10) + filler sanity에 기반한 **잠정** 해석이다. 통계 확정은 더 큰 N에서.

dev smoke는 동일 예산에서 Model Summary가 ISM보다 높은 AR/ES를 보였다. 그러나 이를 "요약이
본질적으로 더 효율적"이라고 단정하기 전에 두 가지를 구분해야 한다. 첫째, smoke의 Model Summary는
다수 셀에서 AR > 1(Full Context 초과)이었는데, filler sanity 점검(같은 10문서, 문서 길이 변화)에서
**filler가 없을 때 요약은 Full Context를 능가하지 못했고(gap −0.05), 중립 filler 길이가 늘수록
gap이 단조 증가(−0.05 → +0.15 → +0.25)**했다. 즉 AR > 1의 상당 부분은 요약의 우월성이 아니라
**긴 중립 filler가 Full Context 추론을 방해한 artifact**다(증거:
[docs/evidence/fixed-budget-filler-sanity/](../docs/evidence/fixed-budget-filler-sanity/README.md)).
둘째, ISM과 요약은 모두 filler를 제거하므로 둘 사이 비교는 이 artifact와 분리된다. dev pilot
(§8.3.2, N=80 문항)의 **같은 문항 paired 비교**에서 Model Summary는 ISM을 모든 예산에서 유의하게
능가했다(\(\Delta\)=+0.25~+0.375, McNemar p<0.01, 512에서 p<1e-6). 즉 full_context 오염을 배제한
직접 비교에서도 요약이 ISM보다 토큰 효율이 높다.

따라서 현 시점의 잠정 결론은 다음과 같다. **dev pilot은 ISM의 차별점이 순수한 토큰 효율이 아니라
검사 가능성(inspectability)과 개입 가능성(intervention)에 있음을 시사한다**(6.1에서 사전 의미내용·
심볼 구조의 기능적 사용이 관찰된 점과 정합적; 6.3에서 동일 예산 효율은 자연어 요약이 우세). 즉 ISM은
"더 효율적인 압축"이라기보다 "경쟁력 있는 압축 + 명시적 개입 가능성"으로 자리매김하는 것이 정직하다.
효율 비교의 최종 확정은 full registered scale에서 수행한다.

### 9.4 실패 결과의 가치

본 연구는 양의 결과만을 전제로 하지 않는다. Symbol Only가 Random과 다르지 않거나, 사전 교환 후 성능이 회복되지 않거나, 자연어 요약이 모든 예산에서 우세할 수 있다. 이러한 결과는 prompt-only 이산 심볼 압축의 한계를 규명하고, 어떤 수준의 학습 또는 잔여 메모리가 필요한지 보여준다.

### 9.5 RQ1에 대한 dev-scale 예비 해석 (초안)

> 본 절은 dev scale-up(§8.1.2, N=240) 결과에 대한 **예비 해석 초안**이며, full registered
> scale 확정 전 잠정 진술이다.

Dev-scale 결과는 부록 A.1의 amended RQ1 기준을 지지한다. 사전의 의미내용을 반전하는
counterfactual corruption은 정확도를 유의하게 낮췄고(\(\Delta_{\mathrm{map}}^{\mathrm{flip}}=+0.079\),
p=0.032), Symbol Only는 Random Symbol을 유의하게 능가했다(\(\Delta_{\mathrm{symbol}}=+0.108\),
p=0.0005). 반면 정의를 라벨 간 순열하는 derangement는 유의한 영향이 없었다(p=0.16). 이는
모델이 **사전의 의미내용과 심볼 관계 구조를 모두 사용하되, 임의의 표면 라벨 바인딩에는
의존하지 않음**을 시사한다.

> Dev-scale results support the amended RQ1 criterion: semantic dictionary corruption
> significantly reduces accuracy, while Symbol Only remains above Random Symbol. This suggests
> that both dictionary semantic content and symbolic relational structure are used by the model.
> However, full registered-scale confirmation remains pending due to sequential compression cost.

또한 이 해석은 초기 dev pilot의 \(\Delta_{\mathrm{map}}\approx0\) 관찰이 가설의 반증이 아니라
(1) 압축기 purity 부족과 (2) 내용 보존적 derangement라는 측정 결함의 산물이었음을 보여준다
(진단: [docs/reviews/llm-ism-diagnostic.md](../docs/reviews/llm-ism-diagnostic.md)). 결함을 교정한
뒤에야 construct-valid contrast가 가설을 지지하는 방향으로 나타났다.

## 10. 한계

첫째, Synthetic Rule-QA의 규칙 구조는 실제 문서보다 명확하고 폐쇄적이다. QASPER를 통해 외적 타당도를 보완하지만, 두 데이터셋만으로 모든 장문 추론 과제에 일반화할 수 없다.

둘째, 텍스트 심볼과 사전은 사람이 검사할 수 있지만 자동으로 해석 가능하거나 충실하다고 보장되지 않는다. 심볼 정의가 원문의 인과 구조를 정확히 반영하는지는 gold graph가 없는 실제 문서에서 완전히 검증하기 어렵다.

셋째, Dictionary Swap에는 소규모 LoRA 학습이 사용되므로 prompt-only 메인 실험과 학습 조건이 다르다. Swap 결과는 학습 없는 일반 능력이 아니라, 제한된 binding 학습 이후의 전이 능력으로 해석해야 한다.

넷째, Efficiency Score는 간결하지만 정확도 보존율을 압축률로 나눈 비율 지표이므로 매우 작은 CR에서 과도하게 커질 수 있다. 따라서 AR-CR 프런티어와 원시 정확도를 항상 함께 보고한다.

다섯째, 실제 시스템 비용은 토큰 수 외에도 압축 생성 비용, KV-cache, 하드웨어, 배치 크기 및 지연 시간의 영향을 받는다. Reuse 실험에서는 압축 생성 비용을 포함한 end-to-end 비용과 serving-only 비용을 분리한다.

여섯째, 현재 RQ1 증거는 dev scale-up(N=240)에서 얻은 것이며 full registered scale(dev 5k)이
아니다. 압축이 문서마다 순차 생성으로 수행되어 비용이 크기 때문으로, full-scale 확정은 압축
batching 등 처리량 개선 이후로 미룬다. 따라서 본 단계의 RQ1 진술은 예비적이다.

## 11. 결론

본 논문은 장문 문서를 재사용 가능한 이산 텍스트 심볼과 사전으로 압축하는 Inspectable Symbolic Compression을 제안한다. ISM의 핵심은 단순히 입력을 줄이는 데 있지 않다. 정상 사전을 제거하거나 오염시키고, 심볼 라벨을 미관측 집합으로 교환함으로써 압축 표현이 실제로 어떤 정보에 의존하는지 시험할 수 있다.

Synthetic Rule-QA에서는 이러한 개입의 원인을 gold rule graph와 함께 분석하고, QASPER에서는 실제 학술 문서에서의 정보 보존 성능을 검증한다. 동일 토큰 예산의 자연어 요약과 LLMLingua-2를 비교하여 효율성을 평가하되, ISM의 주된 차별점은 경쟁적인 압축 성능과 명시적 개입 가능성의 결합으로 정의한다. 실험 결과가 이 가설을 지지하지 않는 경우에도, 본 프로토콜은 이산 심볼 압축이 구조화 요약과 구분되는 조건과 한계를 명확히 드러낼 수 있다.

**진행 상태 (초안).** 현재까지 RQ1(개입에 대한 반응)의 dev-scale 예비 증거를 확보했다(§8.1.2):
사전 의미내용의 counterfactual 손상과 심볼 구조 제거가 각각 정확도를 유의하게 낮추는 반면,
라벨 순열은 영향이 없었다. 이는 ISM이 표면 라벨 암기가 아니라 의미내용과 관계 구조를 사용함을
시사한다. RQ3(동일 예산 효율), RQ2(미관측 라벨 교환), RQ4(재사용 비용)와 RQ1의 full
registered-scale 확정은 후속 작업으로 남는다. 본 결론은 이들 결과가 채워지면 갱신한다.

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

### A.1 Amendment — corruption contrast의 construct validity (dev pilot 진단 후)

> 본 amendment는 등록 규모 평가를 보기 **전에**, dev pilot 진단 결과에 근거하여 사전등록
> 기준을 명시적으로 갱신한 것이다. 원 기준(위 2번)은 기록을 위해 그대로 남긴다. 이는 결과에
> 맞춰 기준을 바꾸는 것이 아니라, 진단을 통해 derangement corruption이 본래 측정하려던
> construct(사전 의미 의존성)를 측정하지 못함을 발견하고, registered-scale 평가 전 construct-valid
> contrast를 재정의하는 것이다. 근거: [docs/reviews/llm-ism-diagnostic.md](../docs/reviews/llm-ism-diagnostic.md),
> [docs/evidence/ablation-qwen7b-strong/](../docs/evidence/ablation-qwen7b-strong/README.md).

**Original criterion.** Full Symbol + Dict should outperform Corrupted Dict.

**Amendment after diagnostic pilot.** The original derangement corruption permutes the
label→definition assignment but preserves the multiset of dictionary definitions, and the
synthetic definitions are self-contained rules whose conclusions do not depend on the
arbitrary `Z` labels. It therefore tests surface *label-binding* rather than *semantic
dictionary dependence*. For the registered-scale evaluation, dictionary dependence is assessed
primarily with **semantic counterfactual corruption**, which flips (HIGH↔LOW, MEDIUM→LOW,
True↔False) or blanks the conclusion-bearing definitions while preserving format and token
budget as much as possible.

**Primary RQ1 criterion (amended).** Full Symbol + Dict > Flipped Dict, **and** Symbol Only >
Random Symbol.

**Secondary diagnostic.** Full Symbol + Dict vs Deranged Dict reports *label-binding*
sensitivity only, not semantic dependence.

세 가지 contrast를 다음 이름으로 분리해 보고한다.

- \(\Delta_{\mathrm{map}}^{\mathrm{derange}}\): label-binding sensitivity (Full+Dict − Deranged Dict)
- \(\Delta_{\mathrm{map}}^{\mathrm{flip}}\): semantic-content sensitivity (Full+Dict − Flipped Dict) — **primary**
- \(\Delta_{\mathrm{symbol}}\): symbolic-structure sensitivity (Symbol Only − Random Symbol)

원 기준 2번의 "Full+Dict > Corrupted"는 이후 \(\Delta_{\mathrm{map}}^{\mathrm{flip}}\)으로
평가하며, \(\Delta_{\mathrm{map}}^{\mathrm{derange}}\)는 보조 진단으로만 보고한다. 효과 크기
경계는 등록 규모 dev 결과 확정 전에 고정한다.

## 부록 B. 후속 연구

본 논문의 범위에서 제외한 후속 방향은 Symbol + Residual Memory, adaptive symbolization, continuous-discrete hybrid compression, embedding slot, RAG 및 멀티턴 대화 적용이다.
