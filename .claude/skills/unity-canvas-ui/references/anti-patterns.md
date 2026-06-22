# Anti-patterns — 실무에서 자주 나오는 실수와 해법

각 항목은 "증상 → 원인 → 해법" 순서로 적혀 있다. 검수 시 이 문서의 패턴을 먼저 훑고, 발견된 것부터 보고한다.

---

## 1. 버튼 안의 Text offset이 음수 (예: left = -40)

**증상**  
- 버튼의 라벨이 버튼 경계 바깥으로 삐져나옴.
- 해상도에 따라 삐져나오는 정도가 달라져 특정 기기에서만 깨져 보임.
- 인스펙터에서 Text의 Left/Right/Top/Bottom 중 하나 이상이 음수.

**원인**  
- 디자이너가 "라벨을 살짝 키우고 싶어서" 음수 offset으로 부모보다 크게 뻗음.
- 또는 버튼 크기를 줄인 뒤 라벨 크기를 그에 맞춰 줄이지 않아서 자동으로 음수 offset이 됨.

**해법**  
1. **Text는 항상 부모(Button) 안쪽에 여백을 두고 stretch**: Left/Right/Top/Bottom 모두 양수. 보통 `padding = 12` 정도.
2. 라벨 텍스트가 길어 버튼에 안 맞으면 두 가지 선택지:
   - 버튼 크기를 키운다 (디자인 재협의).
   - TMP의 Auto Size를 **좁은 범위**로 켠다 (예: 28~34). 기본 끔 권장.
   - Overflow = Ellipsis (`...`)로 자른다.
3. "살짝 키우고 싶은" 의도가 진짜면, 별도 오브젝트(`Label_Decoration`)를 추가해 거기만 음수 offset. 원본 Label은 부모 안쪽 유지.

---

## 2. Anchor가 중앙인데 sizeDelta/anchoredPosition을 픽셀로 박음

**증상**  
- Reference 해상도에서는 완벽하지만 다른 해상도에서 UI 위치가 틀어짐.
- 특히 4K 모니터에서 UI가 중앙에 뭉쳐 있거나, 초저해상도에서 퍼져 있음.

**원인**  
- anchor를 `(0.5, 0.5)` 한 점에 두고 `anchoredPosition = (940, 520)` 식으로 박아서 "중앙 기준 상대 좌표"로 만들어 놓음.
- Canvas Scaler의 scaleFactor는 따라가지만, "오른쪽 위에 붙는다"는 의도가 표현되지 않아서 중앙에서의 거리가 기기마다 달라짐.

**해법**  
- UI가 모서리에 붙어야 하면 anchor를 모서리로 옮긴다 (`(1,1)` 등). Pivot도 같이 맞춘다.
- 전체에 걸쳐 stretch해야 하면 `anchorMin=(0,0), anchorMax=(1,1)`.
- Unity 에디터에서 **Anchor Preset 팝업(rect 좌상단 버튼)** → Alt를 누른 채 프리셋 클릭하면 위치까지 맞춰 재설정된다.

---

## 3. Anchor와 Pivot이 서로 다른 방향

**증상**  
- 회전/스케일 애니메이션이 튐.
- "버튼을 눌렀을 때 살짝 커지는" 애니메이션에서 버튼이 제 위치를 벗어남.
- DOTween 등으로 다루다가 의도하지 않은 위치 이동 발생.

**원인**  
- Anchor를 우상단 `(1,1)`로 옮겼는데 Pivot은 기본값 `(0.5, 0.5)`로 그대로 둠.
- Scale은 pivot을 중심으로 일어나므로 pivot이 중앙이면 rect가 사방으로 퍼지고, pivot이 우상단이면 좌하 방향으로만 커진다. 후자가 UI 의도에 맞는 경우가 많다 — "우상단 모서리에 고정된 상태로 커진다".

**해법**  
- Anchor와 Pivot을 같은 방향으로 맞춘다 (SKILL.md의 권장 조합표 참조).
- 예외: Pivot을 의도적으로 다르게 두는 경우 — 예: 캐릭터 머리 위 이름표를 캐릭터 앵커에서 아래 pivot으로 두어 아래서 위로 올라오는 애니메이션.

---

## 4. Canvas Scaler가 Constant Pixel Size

**증상**  
- 고해상도 모니터에서 UI가 작아 보임.
- 저해상도에서 UI가 커서 화면을 덮음.
- "모니터 바꾸니까 게임 UI가 아예 다르게 보여"

**원인**  
- Canvas 컴포넌트에 Canvas Scaler가 없거나, 있어도 `Constant Pixel Size`로 설정됨.

**해법**  
- `UI Scale Mode = Scale With Screen Size`.
- `Reference Resolution = 1920×1080` (또는 프로젝트 타겟).
- `Screen Match Mode = Match Width Or Height`, `Match = 0.5`.

---

## 5. Layout Group 안에서 자식의 sizeDelta를 수동 조정

**증상**  
- Vertical Layout Group 안에 넣었는데 자식이 원하는 크기로 안 배치됨.
- 이상한 겹침이나 공백 발생.
- LayoutElement를 추가했더니 해결됨 (근데 왜?).

**원인**  
- Layout Group은 자식의 `preferredHeight` / `preferredWidth`를 보고 배치한다. 이 값을 `LayoutElement` 없이 직접 `sizeDelta`에만 박아두면 Layout Group이 자기 계산으로 덮어쓰므로 의도가 반영되지 않는다.

**해법**  
- 자식에 `LayoutElement` 컴포넌트 추가. `Min Height`, `Preferred Height`, `Flexible Height`를 명시.
- Flexible 값을 1 이상 주면 "남는 공간을 이 자식이 차지"한다.

---

## 6. ContentSizeFitter를 Layout Group의 자식에게 넣음

**증상**  
- 레이아웃이 깜빡이거나, 크기가 0으로 수렴, 또는 무한 확장.
- 콘솔에 `Layout loop` 경고.

**원인**  
- 부모 Layout Group은 자식 크기를 강제하고, 자식의 ContentSizeFitter는 자기 크기를 스스로 정하려 하므로 매 프레임 서로 경쟁.

**해법**  
- ContentSizeFitter가 필요한 자식이면 중간에 래퍼 오브젝트를 두어 Layout Group에서 분리.
- 또는 그 자식은 `LayoutElement`로 고정 크기를 주고 ContentSizeFitter 제거.

---

## 7. Image의 Preserve Aspect 누락

**증상**  
- 아이콘이 해상도에 따라 세로로 또는 가로로 찌그러짐.
- 동그란 아바타가 타원이 됨.

**원인**  
- Image 컴포넌트의 `Preserve Aspect` 체크박스가 꺼진 상태에서 부모의 aspect ratio가 이미지와 다름.

**해법**  
- `Preserve Aspect` 체크.
- 아이콘이 정사각 영역에 들어가야 한다면 부모 RectTransform에 `Aspect Ratio Fitter` 컴포넌트 추가.

---

## 8. Safe Area 미적용

**증상**  
- iPhone/최신 Android 기기에서 좌측(가로 모드) 노치에 UI가 가려짐.
- 홈 인디케이터 위에 버튼이 겹침.

**원인**  
- Canvas 바로 아래에 SafeArea 컨테이너 없이 UI를 배치.

**해법**  
- Canvas의 자식으로 SafeArea RectTransform을 두고, 스크립트로 `Screen.safeArea`를 anchorMin/Max 비율로 변환해 매 프레임(또는 해상도 변경 시)에 적용.
- `references/safe-area.md`의 예제 스크립트 사용.

---

## 9. TMP Auto Size를 기본으로 켜두고 min/max를 12~72처럼 넓게 둠

**증상**  
- 같은 버튼 디자인인데 라벨 길이에 따라 폰트 크기가 눈에 띄게 다름.
- UI 일관성 붕괴.

**원인**  
- "안 맞으면 Unity가 알아서 하겠지"로 Auto Size를 켜고 범위를 넓게.

**해법**  
- 기본은 Auto Size 끄기.
- 켜야 하면 min/max 차이를 2~6 포인트로 좁게.
- 라벨 길이가 정말 제어 불가한 경우 Overflow = Ellipsis로 자름.

---

## 10. 하나의 GameObject가 버튼이자 컨테이너

**증상**  
- 버튼의 배경을 바꾸려는데 안쪽 아이콘도 영향받음.
- 버튼의 자식이 또 버튼이라 클릭이 이벤트 버블링으로 꼬임.

**원인**  
- Button 컴포넌트가 붙은 오브젝트 자체에 Image 배경, Text, Icon을 모두 자식으로 둠. 문제는 아니지만, 그 Button 안에 또 다른 상호작용 요소(서브 버튼)가 있으면 역할이 섞임.

**해법**  
- Button = 클릭 영역 + 배경. 
- Button의 자식으로 Label, Icon만.
- 서브 인터랙션이 필요하면 Button을 감싸는 컨테이너를 별도로.

---

## 11. "Reference Resolution"을 낮춰 두고 고해상도를 타겟

**증상**  
- UI 이미지가 흐릿함 (특히 텍스트와 아이콘).

**원인**  
- Reference를 1280×720 같은 저해상도로 두고 실제 게임은 2560×1440으로 실행. 업스케일 발생.

**해법**  
- Reference는 타겟 기기 중 **고해상도 쪽**에 맞춰 설정. 1920×1080 또는 2560×1440.
- 실제 아트 에셋도 Reference 이상의 해상도로 준비.
- Sprite Import Settings의 `Max Size`가 Reference에서 쓸 만큼 충분한지 확인.

---

## 12. 모달인데 Raycast Target을 가진 배경이 없음

**증상**  
- 모달이 떠 있는데 뒤의 버튼이 눌림.

**원인**  
- 모달을 띄울 때 "뒤의 클릭을 막는 투명 배경(Image with alpha=0~0.5, Raycast Target=on)"을 안 둠.

**해법**  
- 모달 루트 바로 아래에 full-stretch Image를 `Raycast Target=on`, 색 `(0,0,0, 0.5)` 또는 완전 투명으로 배치.
- 이 Image가 있어야 뒤의 EventSystem이 클릭을 이 Image에서 받고, 뒤까지 전달하지 않는다.

---

## 13. Scroll View의 Content가 상단 중심 anchor가 아님

**증상**  
- 스크롤이 거꾸로 작동하거나, 내용이 화면에 안 보임.
- Content를 키울 때 아래쪽으로 자람이 아니라 위쪽으로 자라 잘림.

**원인**  
- Scroll View의 Content는 보통 "위에서 아래로 채움" 구조. 이때 pivot은 `(0.5, 1)` (상단 중앙)이어야 ContentSizeFitter가 키웠을 때 아래쪽으로 자란다.

**해법**  
- Content RectTransform:
  - `anchorMin = (0, 1)`, `anchorMax = (1, 1)` (상단 stretch)
  - `pivot = (0.5, 1)`
  - `VerticalLayoutGroup` + `ContentSizeFitter(Vertical = Preferred Size)`

---

## 검수 시 우선순위

위 항목 중 **1, 2, 4, 8**은 critical (해상도 대응이 근본적으로 깨짐).  
**3, 5, 6, 11, 12**는 warning (특정 상황에서 터짐).  
**7, 9, 10, 13**은 주로 특정 기능이 동작 안 하거나 미관 문제.

검수 보고 시 이 우선순위로 정렬해서 제시한다.
