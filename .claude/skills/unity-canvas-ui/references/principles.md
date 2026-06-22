# Unity Canvas UI — 원칙 상세

SKILL.md 본문이 "무엇을, 어떻게"라면 이 문서는 "왜"를 담는다. 원칙을 어기고 싶을 때 — "이 프로젝트는 좀 특이하니까 예외로 하자" — 이 문서를 먼저 읽어서 그 원칙이 왜 있는지 이해하고 판단한다.

## 목차

1. [Canvas Scaler의 수학](#1-canvas-scaler의-수학)
2. [Anchor / Pivot / Offset의 의미](#2-anchor--pivot--offset의-의미)
3. [Stretch가 기본이어야 하는 이유](#3-stretch가-기본이어야-하는-이유)
4. [Hierarchy 설계의 원리](#4-hierarchy-설계의-원리)
5. [Layout Group과 ContentSizeFitter의 결합 규칙](#5-layout-group과-contentsizefitter의-결합-규칙)
6. [TMP의 Auto Size를 조심하는 이유](#6-tmp의-auto-size를-조심하는-이유)
7. [가로 모드 PC/모바일 동시 대응 전략](#7-가로-모드-pc모바일-동시-대응-전략)

---

## 1. Canvas Scaler의 수학

Canvas Scaler의 `Scale With Screen Size` 모드는 내부적으로 이런 계산을 한다 (간략화):

```
scaleFactor =
  screenWidth^(1 - match) * screenHeight^(match)
  / (refWidth^(1 - match) * refHeight^(match))
```

- `match = 0` → `scaleFactor = screenWidth / refWidth` (너비만 본다)
- `match = 1` → `scaleFactor = screenHeight / refHeight` (높이만 본다)
- `match = 0.5` → 두 비율의 기하평균

### 가로 모드에서 Match 값이 의미하는 것

Reference를 1920×1080, match=0.5로 두었다고 하자.

| 기기 | 해상도 | scaleFactor |
|---|---|---|
| 1080p 모니터 | 1920×1080 | 1.000 |
| 1440p 모니터 | 2560×1440 | 1.333 |
| iPad 가로 | 2732×2048 | √(2732/1920 × 2048/1080) ≈ 1.427 |
| 모바일 19.5:9 가로 | 2340×1080 | √(2340/1920 × 1080/1080) ≈ 1.103 |

모든 UI가 해상도에 맞춰 크기만 커지고 비율은 유지된다. 대신 **화면 가장자리의 여백**이 기기마다 달라지므로, 가장자리에 붙는 UI는 anchor를 모서리에 고정해야 한다. 정중앙에 있는 UI는 중앙 anchor만 쓰면 자동으로 중앙에 머문다.

### 왜 Constant Pixel Size는 쓰지 않는가

Constant Pixel Size는 "픽셀 수"를 고정한다. 4K 모니터에서는 UI가 작아지고, 저해상도에서는 커진다. 게임/앱에서는 거의 쓰지 않는다. 쓰는 경우는 디버그 오버레이 정도.

### 왜 Constant Physical Size도 아닌가

이론적으로 "항상 물리적으로 같은 크기"를 보장하지만, 모니터 DPI가 OS마다 부정확하게 보고되어 실무에서 믿을 수 없다. 모바일도 DPI 값이 제조사마다 들쭉날쭉하다.

---

## 2. Anchor / Pivot / Offset의 의미

RectTransform은 세 가지를 기억한다: **Anchor**, **Pivot**, **Offset**.

- **Anchor (`anchorMin`, `anchorMax`)**: 부모의 "어떤 지점"에 붙을지. (0,0)은 부모의 왼쪽 아래, (1,1)은 오른쪽 위. min과 max가 같으면 "한 점에 붙음"이고, 다르면 "그 영역에 stretch".
- **Pivot**: 이 RectTransform 자신의 "회전/스케일 중심". (0,0)은 자기의 왼쪽 아래.
- **Offset (`offsetMin`, `offsetMax`)**: anchor 지점으로부터의 거리.

### anchor가 한 점일 때 (min == max)

`anchoredPosition`과 `sizeDelta`가 의미를 가진다.
- `anchoredPosition`: anchor 지점에서 pivot까지의 거리 (픽셀).
- `sizeDelta`: 이 rect의 크기 (픽셀).

### anchor가 영역일 때 (min != max)

`anchoredPosition`과 `sizeDelta`는 의미가 달라진다.
- `offsetMin = (left, bottom)`: anchor 영역 왼쪽 아래 모서리로부터의 offset.
- `offsetMax = (-right, -top)`: anchor 영역 오른쪽 위 모서리로부터의 offset (여백이면 음수).

Unity 인스펙터는 이 둘을 합쳐서 `Left / Top / Right / Bottom`으로 보여준다. 우리가 "여백"이라고 부르는 것은 이 네 값이다.

### 핵심 통찰

`left`, `right`, `top`, `bottom`이 **양수**라는 것은 "부모 경계로부터 안쪽으로 들어와 있다"는 뜻이다. **음수**는 "부모 경계 바깥으로 튀어나와 있다"는 뜻이다.

디자인 의도로 바깥으로 튀어나와야 하는 경우(그림자, 장식)를 제외하면, 음수는 항상 버그의 징후로 본다.

---

## 3. Stretch가 기본이어야 하는 이유

초보자는 anchor를 모두 `(0.5, 0.5)`로 두고 `anchoredPosition`에 픽셀 좌표를 직접 박는 경향이 있다. Unity 에디터의 기본값이 그래서다. 이 방식은 **Reference Resolution과 100% 똑같은 해상도에서만** 정상이다.

1920×1080 기준으로 "오른쪽 위에서 20픽셀 떨어진 곳"에 아이콘을 놓았다고 하자. anchor=(0.5,0.5), position=(940, 520). 이걸 2560×1440 화면에서 보면, Canvas Scaler가 scaleFactor를 1.333배 주므로 아이콘은 중앙에서 1.333×940 떨어진 곳에 있게 된다. 그 거리는 여전히 "오른쪽 위 근처"지만, 중앙을 기준으로 한 상대 좌표다. UI가 "오른쪽 위에 붙어야" 한다는 원래 의도를 시스템은 모른다.

반면 anchor를 `(1, 1)`에 두고 position=(-20, -20)으로 하면, 어떤 해상도에서도 "오른쪽 위 모서리에서 20px 떨어진 곳"이다. Canvas Scaler가 scaleFactor를 바꿔도 상대 관계가 유지된다.

### 결론

**UI 요소의 위치는 "픽셀 좌표"가 아니라 "부모에 대한 관계"로 표현해야 한다.** Anchor가 그 관계를 표현하는 수단이다. Stretch는 관계 중에서도 가장 강한 형태 — "부모와 함께 늘어난다"다.

---

## 4. Hierarchy 설계의 원리

Hierarchy는 코드의 함수 구조와 같다. 역할이 잘 나뉘면 수정이 쉽고, 섞여 있으면 어디를 만져야 할지 모른다.

### 레이어 분리

HUD(항상 보이는 정보), 현재 화면, 모달, 토스트 — 이 네 가지는 기본적으로 충돌하는 관심사다.
- HUD는 모달이 뜨는 중에도 보여야 할 수 있다 (또는 숨겨야 할 수 있다).
- 모달은 현재 화면 위에 그려져야 한다.
- 토스트는 모달 위에도 뜬다.

이 충돌을 sibling index(Hierarchy 내 순서)로 제어하려면 레이어가 형제로 나란히 있어야 한다. 레이어를 중첩하면(예: 모달이 현재 화면의 자식이면) 현재 화면을 숨기는 순간 모달도 같이 사라지는 실수가 나온다.

### "하나의 GameObject에 두 역할 금지"

특히 버튼과 컨테이너의 겸임이 실수의 온상이다. "이 패널이 클릭하면 반응하는 버튼이기도 하다"는 구조는 나중에 "클릭 영역은 그대로 두고 배경만 바꾸고 싶다"가 되면 복잡해진다. 버튼은 버튼, 컨테이너는 컨테이너로 나누고, 필요하면 스크립트로 묶는다.

### RectTransform 계층이 깊어질수록 계산 비용

Layout Group이 있는 계층이 중첩될수록 한 프레임의 layout rebuild 비용이 누적된다. 세 단계를 넘는 중첩은 피한다.

---

## 5. Layout Group과 ContentSizeFitter의 결합 규칙

둘을 같이 쓸 때 헷갈리는 지점이 있다. 원칙을 명확히 한다.

- **Layout Group** (Vertical/Horizontal/Grid): **자식들의 위치와 크기를 계산**한다.
- **ContentSizeFitter**: **자신(이 게임오브젝트)의 RectTransform 크기를 자식들에 맞춰 조절**한다.

### 조합 패턴

**(a) 고정 크기 컨테이너에 가변 자식 배치**: Layout Group만. ContentSizeFitter 없음. 컨테이너의 크기는 anchor/offset으로 지정, 자식 크기는 LayoutElement로 제어.

**(b) 내용 크기에 컨테이너가 맞춰짐**: Layout Group + ContentSizeFitter(Preferred Size). 예: 툴팁, 길이 가변 다이얼로그.

**(c) Scroll View의 Content**: Layout Group + ContentSizeFitter(Preferred Size, 주로 Vertical만). Viewport가 잘라내고, Content는 자식 합 크기만큼 자라야 스크롤이 작동.

### 주의점

- ContentSizeFitter를 쓰는 RectTransform은 Layout Group의 영향으로 크기가 정해지는 자식이면 안 된다. Layout Group은 자식 크기를 강제하고, ContentSizeFitter는 자기 크기를 자기가 계산하므로 충돌한다.
- 이 경우 LayoutElement에 `Ignore Layout = true`를 주거나, 중간에 래퍼 오브젝트를 한 단계 넣어서 분리한다.
- `Layout Element`의 `Preferred`가 자식들의 자연스런 크기를 반영하게 하려면, 자식들에게도 적절한 LayoutElement가 있어야 재귀적으로 전파된다.

---

## 6. TMP의 Auto Size를 조심하는 이유

TextMeshPro의 Auto Size는 "텍스트가 Rect에 맞지 않으면 폰트 크기를 줄여서 맞춤"이다. 편리해 보이지만 몇 가지 함정이 있다.

1. **UI 일관성 붕괴**: 같은 버튼인데 "확인"은 크게, "계속하기"는 약간 작게, "이전 설정으로 되돌리기"는 눈에 띄게 작게 나온다. 시각적 위계가 무너진다.
2. **레이아웃 재계산 비용**: Auto Size는 매번 fit을 시도하므로 텍스트가 자주 바뀌는 UI(타이머, 스코어)에서는 성능이 떨어진다.
3. **디자인 의도 은폐**: "이 버튼의 라벨이 너무 길다"는 신호를 Auto Size가 먹어버린다. 디자이너/기획자가 라벨을 줄이거나 버튼을 키우는 의사결정을 내릴 기회가 사라진다.

### 권장 사용법

- Min/Max를 좁게 (예: 28~34). 2~3 포인트 내에서만 움직이도록.
- 기본은 끄고 쓴다. 켜야 하는 경우는 "다국어 지원으로 라벨 길이가 예측 불가한 경우"로 제한한다.
- 라벨이 잘려도 되는 경우 Auto Size 대신 Overflow = Ellipsis를 쓴다.

---

## 7. 가로 모드 PC/모바일 동시 대응 전략

PC 가로는 보통 16:9 또는 21:9. 모바일 가로는 19.5:9, 20:9 등 훨씬 길쭉하다. Reference를 1920×1080(16:9)으로 두고 match=0.5로 두면 다음이 보장된다.

- **중앙부 콘텐츠**는 항상 중앙에 머문다 (anchor center).
- **모서리 UI**는 모서리에 머문다 (anchor corner).
- **전체 stretch 배경**은 화면을 가득 채운다.

대신 다음 항목은 **해상도별로 "비어 있는 공간"이 달라진다**는 것을 의식해야 한다.

- 21:9 PC 모니터에서는 좌우에 추가 공간 생김 → 좌우 모서리 UI가 중앙 콘텐츠와 멀어짐.
- 19.5:9 모바일에서는 좌우가 더 늘어남 → 마찬가지.
- 16:9보다 좁은 비율(4:3, 아이패드 가로)에서는 상하 공간이 더 생김.

### 실전 가이드

1. **중요 HUD(체력바, 미니맵 등)는 모서리 anchor**. 비율이 바뀌어도 붙어 있다.
2. **주요 액션 버튼은 중앙 또는 화면 중심에서 일정 거리 이내**. 모서리에 두면 길쭉한 화면에서 엄지에 안 닿는다.
3. **배경/패널은 full stretch**. 반드시 모든 해상도에서 채워져야 한다.
4. **텍스트 영역은 Reference 기준으로 짜고, 모바일에서는 폰트를 살짝 키울 수 있도록 프로필 준비**. 런타임에 Platform별 Canvas Scaler 설정을 바꾸는 것도 한 방법.
5. **Safe Area 필수**. 모바일 가로 모드에서 노치가 좌/우 어느 쪽에 오는지 기기마다 다르다.

### 테스트 매트릭스 최소 권장

- 1920×1080 (16:9 PC 기본)
- 2560×1080 (21:9 울트라와이드)
- 2340×1080 (19.5:9 모바일, 예: 요즘 Android 가로)
- 2732×2048 (4:3 아이패드 가로)
- 1366×768 (구형 노트북)

이 다섯 가지에서 UI가 모두 의도대로 보이면 대부분의 기기를 커버한다.
