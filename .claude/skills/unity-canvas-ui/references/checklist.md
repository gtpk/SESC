# UI 생성/수정 후 자가 검수 체크리스트

새 UI를 만들거나 기존 UI를 수정한 직후, 이 체크리스트를 위에서부터 훑어 각 항목을 확인한다. 하나라도 실패하면 그 단계에서 멈추고 수정한다.

## Canvas 레벨

- [ ] Canvas Scaler의 UI Scale Mode가 `Scale With Screen Size`인가?
- [ ] Reference Resolution이 타겟 중 가장 높은 쪽(최소 1920×1080)으로 설정되어 있는가?
- [ ] Screen Match Mode가 `Match Width Or Height`이고 Match=0.5 (또는 의도된 값)인가?
- [ ] SafeArea 컨테이너가 Canvas 바로 아래에 있는가? (모바일 타겟인 경우 필수)

## RectTransform 레벨 — 각 UI 요소마다

- [ ] Anchor가 "이 요소가 어디에 붙어야 하는가"를 표현하는가? (중앙이면 중앙, 모서리면 모서리, stretch면 stretch)
- [ ] Pivot이 Anchor와 같은 방향인가? (권장 조합표 참조)
- [ ] Stretch anchor를 쓴다면 left/right/top/bottom이 모두 0 이상(양수 또는 0)인가?
- [ ] 음수 offset이 있다면 그것이 "의도적 오버플로우"인가? 아니면 실수인가?
- [ ] anchoredPosition이 "해상도 독립적인 모서리 기준 거리"로 해석되는가? (중앙 anchor에 절대 좌표 박기 금지)

## Button 레벨

- [ ] Button 자체는 클릭 영역 + 배경만 담당하는가?
- [ ] Label(Text/TMP)은 Button의 자식이고, anchor stretch + 양수 padding으로 배치되어 있는가?
- [ ] Icon이 있다면 Preserve Aspect가 켜져 있는가?
- [ ] 라벨이 긴 경우에 대한 대응책(폰트 Auto Size 좁은 범위 / Overflow Ellipsis / 버튼 크기 증가)이 정해져 있는가?

## Text / TMP 레벨

- [ ] Auto Size가 꺼져 있거나, 켜져 있다면 min/max 차이가 좁은가 (예: 28~34)?
- [ ] Overflow 설정이 용도에 맞는가? (버튼 라벨 = Ellipsis/Truncate, 단락 = Overflow + Fitter)
- [ ] 한/영/숫자가 섞이는 경우 Fallback Font Asset이 구성되어 있는가?

## Layout Group / Scroll View 레벨

- [ ] Layout Group 자식에 ContentSizeFitter를 쓰고 있지 않은가? (쓰면 loop 경고 발생)
- [ ] Layout Group 자식들에 `LayoutElement`로 minHeight/preferredHeight가 명시되어 있는가?
- [ ] Scroll View의 Content가 상단 stretch anchor(+ pivot (0.5, 1))이고 ContentSizeFitter(Vertical=Preferred)가 붙어 있는가?
- [ ] Scroll View의 Viewport에 Mask가 있고 anchor stretch + offset=0인가?

## 모달 / 레이어 레벨

- [ ] 모달 루트 바로 아래에 full-stretch Raycast Target 배경이 있는가?
- [ ] 모달 / 토스트 / 현재 화면이 형제 관계인가, 아니면 중첩돼 있는가? (중첩이면 레이어 분리 검토)

## 해상도 테스트

최소 다음 해상도에서 모두 의도대로 보이는지 확인:

- [ ] 1920×1080 (16:9 PC 기본)
- [ ] 2560×1080 (21:9 울트라와이드) — UI가 좌우 모서리에서 떨어져 보이는가?
- [ ] 2340×1080 (19.5:9 모바일 가로) — HUD가 안전 영역 안에 있는가?
- [ ] 2732×2048 (4:3 태블릿 가로) — 상하가 남는데 UI가 세로로 자연스럽게 배치되는가?
- [ ] 1366×768 (구형 노트북) — 작아진 환경에서 텍스트가 읽히는가?

Unity 에디터의 Game 뷰 왼쪽 위 해상도 드롭다운에서 각 프리셋을 추가해 빠르게 전환할 수 있다.

## 상호작용 테스트

- [ ] 버튼을 터치했을 때 피드백(색 변경, 스케일)이 자연스러운가?
- [ ] Scroll View가 모든 방향으로 예상대로 스크롤되는가?
- [ ] 모달이 뜨면 뒤의 UI가 눌리지 않는가?
- [ ] 해상도가 런타임에 바뀌었을 때 (창 크기 조절 등) UI가 재배치되는가?

## 최종 점검

- [ ] 변경된 prefab/scene 파일을 저장했는가?
- [ ] 의도적으로 규칙을 깬 부분이 있다면 네이밍(`_Overflow`, `_Shadow`)이나 주석으로 의도를 남겼는가?
- [ ] 스크립트(예: SafeAreaFitter)가 참조하는 경로/태그가 깨지지 않았는가?
