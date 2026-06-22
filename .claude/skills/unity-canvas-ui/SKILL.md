---
name: unity-canvas-ui
description: Unity의 uGUI Canvas 기반 UI를 해상도에 유연하게(PC/모바일 가로 모두) 설계, 검수, 수정하는 원칙과 도구 모음. 사용자가 Unity UI, Canvas, RectTransform, anchor, pivot, stretch, Button, TextMeshPro, prefab 정렬, 버튼 안의 Text가 튀어나옴, 해상도별로 UI가 깨짐 같은 주제를 언급하거나, Unity 프로젝트의 .prefab/.unity 파일을 fit되도록 수정하려 할 때 반드시 사용한다. "UI가 안 맞는다", "버튼 안의 텍스트가 이상하다", "해상도별로 레이아웃이 깨진다"는 식의 증상 기반 요청에도 적극적으로 트리거한다.
---

# Unity Canvas UI — 해상도에 유연한 레이아웃 원칙과 검수

이 skill은 Unity uGUI(Canvas) 기반 UI를 "여러 해상도에서 의도대로 보이게" 만드는 것을 목표로 한다. 가로 모드 기준으로 PC와 모바일 양쪽을 동시에 커버하는 프로젝트에 초점이 맞춰져 있다.

## 언제 무엇을 하는가

사용자 요청을 크게 세 가지로 나눠 대응한다.

**(A) 기존 UI 검수/수정** — "이 prefab 좀 봐줘", "이 버튼 안 텍스트가 튀어나와", "해상도 바꾸니까 깨져"
- `scripts/audit_unity_ui.py`로 대상 파일(.prefab, .unity)을 스캔해 위반 목록을 뽑는다.
- 위반별로 `references/anti-patterns.md`의 해법을 제시한다.
- 수정을 진행할 때는 YAML을 직접 편집하되, Unity의 fileID/anchor 필드 규칙을 보존한다 (`references/yaml-editing.md` 참조).

**(B) 새 UI 생성 가이드** — "버튼 새로 만드는 템플릿 알려줘", "Canvas 처음부터 세팅해줘"
- `references/principles.md`의 원칙을 순서대로 적용한다.
- `references/checklist.md`의 체크리스트로 자기 검증한다.

**(C) 원칙 해설** — "왜 이렇게 해야 해?", "anchor랑 pivot 차이가 뭐야?"
- SKILL.md 본문의 핵심 원칙과 `references/principles.md`의 근거를 설명한다.
- 추상적 설명보다 "이 원칙을 어기면 어떤 증상이 나타나는가"로 이어서 설명한다.

## 핵심 원칙 (요약)

### 1. Canvas Scaler는 맨 먼저 정한다

해상도 대응의 80%는 Canvas Scaler에서 결정된다. 제대로 안 하면 이후 anchor 작업이 전부 무의미해진다.

- **UI Scale Mode**: `Scale With Screen Size` (고정, 다른 선택지는 예외적인 경우에만)
- **Reference Resolution**: 가로 모드 기본값 `1920 x 1080`. 프로젝트가 더 높은 해상도를 타겟하면 `2560 x 1440`. 이보다 낮추지 말 것 — Reference가 낮으면 고해상도 기기에서 업스케일되어 흐릿해진다.
- **Screen Match Mode**: `Match Width Or Height`
- **Match**: `0.5`가 기본. 가로 모드인데 모바일과 PC를 동시에 커버해야 한다면, aspect ratio가 양쪽 비율 사이에서 움직이므로 0.5가 가장 안전하다. 순수 PC 전용(16:9 고정)이면 0 또는 1 어느 쪽이어도 상관없지만 0.5로 둬도 무방하다.

**이유**: Match를 0(Width)로 두면 세로 공간이 남거나 모자란 기기에서 UI가 잘리거나 뜬다. Match를 1(Height)로 두면 반대로 가로가 잘린다. 0.5는 두 축의 영향을 평균내서 양쪽 모두 어느 정도 보이도록 한다. 실무에서 가장 안전한 기본값이다.

### 2. "부모에 fit" 은 Stretch anchor + 양수 offset

자식이 부모의 크기에 따라 늘어나야 한다면, 항상 이 조합을 쓴다.

- `anchorMin = (0, 0)`, `anchorMax = (1, 1)` — 양 축 stretch
- `offsetMin = (left, bottom)`, `offsetMax = (-right, -top)` — 여백
- 중요: left/bottom은 **양수**, right/top도 **양수**여야 한다 (`offsetMax`에서는 부호가 뒤집혀 음수로 저장됨)
- **여백이 0이면 `(0,0,0,0)`**, 여백이 20픽셀이면 `left=20, right=20, top=20, bottom=20`

**"left가 -40"이 문제인 이유**: Stretch anchor에서 left가 음수라는 것은 자식이 부모의 왼쪽 경계보다 40픽셀 바깥까지 뻗어 있다는 뜻이다. 버튼의 Text가 이런 상태면, 텍스트가 버튼 밖으로 삐져나온다. 해상도가 바뀌어 버튼 크기가 달라지면 삐져나오는 양도 달라지므로 "어떤 기기에서는 괜찮은데 어떤 기기에서는 깨진다"는 현상이 된다.

**허용되는 음수 offset**: 의도적으로 부모보다 크게 그려야 하는 경우 — 예: 배경 그림자, 프레임 장식, 탭 활성화 시 살짝 튀어나오는 하이라이트. 이때는 코드 주석이나 네이밍(`..._Overflow`, `..._Shadow`)으로 의도를 명시한다.

### 3. Anchor와 Pivot은 같은 방향을 가리켜야 한다

Anchor는 "부모의 어디에 붙을 것인가"이고 Pivot은 "내 자신의 어디를 기준점으로 삼을 것인가"다. 둘이 다른 방향이면 회전/스케일/애니메이션 시 예측 불가능한 튕김이 생긴다.

권장 조합:

| 배치 의도 | Anchor (min=max) | Pivot |
|---|---|---|
| 좌상단 고정 | (0, 1) | (0, 1) |
| 상단 중앙 | (0.5, 1) | (0.5, 1) |
| 우상단 고정 | (1, 1) | (1, 1) |
| 정중앙 | (0.5, 0.5) | (0.5, 0.5) |
| 좌하단 고정 | (0, 0) | (0, 0) |
| 우하단 고정 | (1, 0) | (1, 0) |
| 상단 stretch (좌우 늘림) | min(0,1) max(1,1) | (0.5, 1) |
| 하단 stretch | min(0,0) max(1,0) | (0.5, 0) |
| 전체 stretch | min(0,0) max(1,1) | (0.5, 0.5) |

### 4. 계층(Hierarchy) 규칙

의미 없이 중첩하지 말고, 각 레벨에 역할을 준다.

```
Canvas (CanvasScaler 설정)
└── SafeArea (런타임에 Screen.safeArea로 anchor 재설정)
    ├── HUD           (항상 보이는 정보)
    ├── ScreenRoot    (현재 화면)
    │   └── [Button, Panel, List ...]
    ├── ModalLayer    (다이얼로그)
    └── ToastLayer    (알림)
```

- 각 레이어는 **stretch anchor + offsetMin/Max = 0**으로 부모를 완전히 채운다.
- 형제 간 z-order는 Hierarchy 순서로 제어 — `SetAsLastSibling()`으로 모달 띄우기.
- 하나의 GameObject가 두 가지 역할(예: "버튼이자 컨테이너")을 겸하지 않는다. 버튼은 버튼, 컨테이너는 컨테이너로 분리.

### 5. Button 내부 Text/Icon 원칙

**버튼은 세 가지 역할 분리**: (1) 클릭 영역(Button + Image 배경), (2) 라벨(Text/TMP), (3) 아이콘(Image).

```
Button (RectTransform: 원하는 사이즈. 예: 240x72)
├── Background (Image) — anchor stretch, offset=0 (버튼 전체 덮음)
├── Icon (Image)       — anchor (0, 0.5) pivot (0, 0.5), 좌측 여백 고정
└── Label (TMP)        — anchor stretch, offset(left=padding+iconSpace, right=padding, top=padding, bottom=padding) 모두 양수
```

- **Label의 left/right/top/bottom은 항상 양수(여백)**. 음수가 나오면 즉시 시정 대상이다.
- 라벨이 버튼보다 길어지면 폰트 Auto Size (좁은 범위: 예 28~36) 또는 Overflow 모드로 잘라낸다. 음수 offset으로 해결하지 말 것.
- 아이콘은 `Preserve Aspect` 켜두어 해상도에 따라 찌그러지지 않도록 한다.

### 6. List / Scroll 컨테이너 원칙

```
Scroll View
├── Viewport (Mask, anchor stretch, offset=0)
│   └── Content (RectTransform, anchor top-stretch, pivot(0.5,1))
│       + VerticalLayoutGroup (padding, spacing)
│       + ContentSizeFitter (Vertical=Preferred Size)
│       └── Item × N
│            + LayoutElement (minHeight/preferredHeight 명시)
└── Scrollbar (선택)
```

- Content의 크기는 LayoutGroup + ContentSizeFitter가 계산한다. 수동으로 sizeDelta 만지지 않는다.
- Item은 **LayoutElement로 최소/선호 사이즈를 명시**해야 Layout Group이 예상대로 배치한다.
- Item 내부의 Text가 가변 길이라면 Item 자체도 ContentSizeFitter(Vertical=Preferred)를 줄 수 있지만, 이중 중첩은 성능과 재계산 빈도를 늘리므로 정말 필요할 때만.

### 7. TextMeshPro 원칙

- **Auto Size는 "보험"이지 설계가 아니다**. Min/Max를 **좁게** (예: 28~34) 잡아서 폰트 크기가 크게 튀지 않도록 한다. Min과 Max를 12~72처럼 넓게 잡으면 짧은 텍스트는 거대하게, 긴 텍스트는 찌그러지듯 작게 나와서 UI 일관성이 깨진다.
- **Overflow**: 카드/버튼 라벨은 `Ellipsis` 또는 `Truncate`. 말풍선/설명은 `Overflow` 허용하고 부모에 ContentSizeFitter.
- **정렬**: 버튼 라벨은 `Middle-Center`가 기본. 단락은 `Top-Left`.
- **폰트 에셋**: 한/영/숫자/이모지가 섞이는 UI라면 Fallback Font Asset 체인을 미리 구성해 둔다.

### 8. Safe Area 처리

노치/홈바가 있는 기기를 타겟한다면 Canvas 바로 아래 SafeArea 컨테이너를 두고 런타임에 `Screen.safeArea`로 anchor를 맞춘다. 디자인 단계에서도 SafeArea 컨테이너를 reference로 쓰고, 그 안쪽에서 모든 UI를 배치한다.

구체 구현은 `references/safe-area.md`에 있는 스크립트를 쓴다. 에디터에서는 `Game` 뷰의 Aspect 설정을 Safe Area 포함 프리셋으로 바꿔가며 확인한다.

## 검수 워크플로

사용자가 "이 UI 봐줘" 류 요청을 하면:

1. **대상 파일 확보** — `.prefab` 또는 `.unity` 경로. 사용자가 파일을 업로드했거나 프로젝트 폴더를 선택했다면 `/sessions/vibrant-trusting-hamilton/mnt/uploads` 또는 마운트된 폴더에서 찾는다.
2. **스크립트 실행**:
   ```bash
   python3 /sessions/vibrant-trusting-hamilton/mnt/.claude/skills/unity-canvas-ui/scripts/audit_unity_ui.py <file_path>
   ```
   출력은 JSON. 각 위반은 `{gameObject, component, issue, severity, suggestion}` 필드를 갖는다.
3. **보고서 작성** — 치명적(critical) / 경고(warning) / 정보(info)로 나눠 사용자에게 설명. 음수 offset은 critical. Anchor-Pivot 불일치는 warning. Match값 미설정은 info.
4. **수정 제안** — 위반별 수정 YAML 패치를 제시. 사용자가 승인하면 Edit 툴로 파일 직접 수정.

## 새 UI 생성 워크플로

사용자가 "버튼 만들어줘", "HUD 만들어줘" 류 요청을 하면:

1. **`references/principles.md`** 읽어 원칙을 머릿속에 로드한다.
2. **Hierarchy 스케치** — 어떤 계층으로 구성할지 먼저 글로 제안하고 사용자 확인받는다.
3. **템플릿 적용** — `assets/templates/` 아래의 YAML 스니펫(Canvas, Button, ScrollView 등)을 베이스로 수치만 바꿔 쓴다.
4. **체크리스트 자가 검수** — `references/checklist.md`를 따라 스스로 점검.

## 참조 파일

- `references/principles.md` — 원칙 상세와 근거, 이유
- `references/anti-patterns.md` — 실무에서 자주 나오는 실수와 각각의 해법
- `references/checklist.md` — UI 생성/수정 후 자가 검수용 체크리스트
- `references/yaml-editing.md` — Unity .prefab/.unity 파일 구조와 안전하게 편집하는 법
- `references/safe-area.md` — Safe Area 런타임 적용 패턴
- `scripts/audit_unity_ui.py` — prefab/scene 검사 스크립트

참조 파일은 필요할 때만 읽는다. 예를 들어 사용자가 "이 버튼의 텍스트가 삐져나와"라고 하면 `anti-patterns.md`의 해당 섹션만 읽고, 전체 원칙 해설이 필요해지면 그때 `principles.md`를 편다.

## 커뮤니케이션 규칙

- 사용자의 말투가 한국어면 한국어로, 영어면 영어로 답한다. 혼용도 그대로 받아 쓴다.
- 원칙을 제시할 때는 **왜 그렇게 하는지**를 같이 준다. "이렇게 하세요"만 반복하면 사용자가 예외 상황에서 판단할 수 없다.
- 숫자(예: Reference Resolution 1920x1080, Match 0.5)는 "합리적 기본값"으로 제시하되, 프로젝트 상황에 따라 달라질 수 있음을 밝힌다.
- 수정을 할 때는 원본을 덮어쓰기 전에 변경사항을 diff 형태로 보여주고 승인을 받는다.
