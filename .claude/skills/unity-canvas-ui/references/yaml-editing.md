# Unity .prefab / .unity 파일 편집 가이드

Unity의 prefab과 scene 파일은 YAML 포맷이다(정확히는 Unity 독자 확장이 있는 YAML). 텍스트 편집기로 열어서 수정하는 것이 가능하지만, 몇 가지 규칙을 지켜야 Unity가 파일을 망가진 것으로 인식하지 않는다.

## 파일 구조 개요

```yaml
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &12345678901234567
GameObject:
  m_ObjectHideFlags: 0
  m_Name: MyButton
  m_Component:
  - component: {fileID: 12345678901234568}   # RectTransform
  - component: {fileID: 12345678901234569}   # Image
  - component: {fileID: 12345678901234570}   # Button
--- !u!224 &12345678901234568
RectTransform:
  m_GameObject: {fileID: 12345678901234567}
  m_AnchorMin: {x: 0, y: 0}
  m_AnchorMax: {x: 1, y: 1}
  m_AnchoredPosition: {x: 0, y: 0}
  m_SizeDelta: {x: 0, y: 0}
  m_Pivot: {x: 0.5, y: 0.5}
  m_Father: {fileID: 87654321098765432}
  m_Children:
  - {fileID: ...}
```

### 핵심 필드

| 필드 | 의미 |
|---|---|
| `--- !u!224 &FILE_ID` | RectTransform 컴포넌트 (type id 224). `&` 뒤가 이 노드의 fileID. |
| `--- !u!114 &...` | MonoBehaviour (커스텀 스크립트 포함) |
| `--- !u!1 &...` | GameObject |
| `m_AnchorMin / m_AnchorMax` | Anchor 벡터. x/y 각각 0~1. |
| `m_AnchoredPosition` | anchor 기준 위치 (anchor가 한 점일 때 의미 있음) |
| `m_SizeDelta` | anchor가 한 점일 때 = 크기. stretch일 때 = 여백 합산치 (주의!) |
| `m_Pivot` | pivot 벡터 |
| `m_Father` | 부모 Transform의 fileID |
| `m_Children` | 자식 Transform의 fileID 목록 |

### Stretch anchor일 때 SizeDelta의 의미

anchorMin != anchorMax인 경우:
- `m_SizeDelta.x` = (anchorMax.x - anchorMin.x) * parentWidth에서 "얼마만큼 더(또는 덜) 크게 할지". 0이면 정확히 anchor 영역 크기.
- `offsetMin = anchoredPosition - sizeDelta * pivot`
- `offsetMax = anchoredPosition + sizeDelta * (1 - pivot)`

그래서 "left/right/top/bottom"을 YAML에서 직접 읽으려면 계산이 필요하다. `scripts/audit_unity_ui.py`가 이 계산을 해서 사용자에게 친숙한 left/right/top/bottom 값으로 보여준다.

## 편집 시 지켜야 할 규칙

### 1. fileID를 건드리지 않는다

각 컴포넌트는 고유한 fileID로 식별된다. 이 값을 바꾸면 참조가 전부 깨진다. 값만 수정하고 fileID/포인터는 절대 변경하지 않는다.

### 2. 공백과 들여쓰기를 보존한다

YAML은 들여쓰기에 민감하다. Unity는 2-space 들여쓰기를 쓴다. 탭은 금지.

### 3. 수치 형식 유지

- `m_AnchorMin: {x: 0, y: 0}` — 정수면 정수로, 소수면 소수로.
- `0.5`를 `.5`로 쓰지 않는다.
- 벡터는 인라인 맵핑 `{x: a, y: b}` 형식.

### 4. 대소문자와 스펠링 정확히

`m_AnchorMin`을 `m_Anchormin`으로 잘못 쓰면 Unity가 해당 필드를 무시한다. 기본값으로 덮어쓰기도 함.

## 일반적인 수정 패턴

### Stretch anchor + 여백 20으로 수정

부모 크기 기준 여백 20을 주고 싶다면, **값을 직접 계산해서 박는 것이 아니라** anchor를 stretch로, offset을 padding으로 설정:

- `m_AnchorMin: {x: 0, y: 0}`
- `m_AnchorMax: {x: 1, y: 1}`
- `m_Pivot: {x: 0.5, y: 0.5}`

여백 = `left=right=top=bottom=20` 상황에서 SizeDelta/AnchoredPosition:
- `m_AnchoredPosition: {x: 0, y: 0}` (중앙)
- `m_SizeDelta: {x: -40, y: -40}` (좌우 합 40, 상하 합 40을 줄임)

**중요**: SizeDelta가 음수가 되는 것은 stretch anchor에서 정상이다. "자기 영역보다 얼마나 줄어들어 있는가"를 뜻한다. 이건 anti-pattern이 아니다. 우리가 싫어하는 것은 "stretch인데 offset(left/right/top/bottom)이 음수"인 경우다.

### Anchor Preset "좌상단"으로 바꾸기 (한 점 anchor)

- `m_AnchorMin: {x: 0, y: 1}`
- `m_AnchorMax: {x: 0, y: 1}`
- `m_Pivot: {x: 0, y: 1}`
- `m_AnchoredPosition: {x: 10, y: -10}` (좌상단에서 우하로 10, 10)
- `m_SizeDelta: {x: 120, y: 40}` (크기 고정)

## 안전한 편집 절차

1. **원본 백업**: 편집 전 `.prefab`을 `.prefab.bak`으로 복사.
2. **Edit 툴로 값만 바꾸기**: 가능한 한 작은 단위로. 하나의 필드 수정이 하나의 Edit 호출.
3. **diff 확인**: 수정 후 git diff 또는 `diff` 명령어로 변경 범위가 예상대로인지 검사. fileID가 바뀌었다면 롤백.
4. **Unity에서 열기 테스트**: 가능하면 Unity에서 직접 열어 에러 없이 로드되는지 확인.

## Scene(.unity) 파일은 특히 조심

Scene 파일은 prefab보다 크고, 컴포넌트 간 참조가 복잡하다. Scene 편집이 필요하면 항상 prefab으로 분리할 수 없는지 먼저 검토. 예를 들어 "이 Canvas 하위의 공용 UI는 prefab으로 만들자"가 scene 직접 편집보다 나은 선택이다.

## Claude가 편집을 진행하는 기본 절차

1. `scripts/audit_unity_ui.py`로 위반 목록 생성.
2. 사용자에게 위반 목록과 제안을 제시, 승인 받기.
3. 각 위반별로 Edit 툴로 **하나씩** 수정. 한 번의 Edit에 여러 위반을 몰아 처리하지 않는다 (실수 복구 어려움).
4. 각 Edit 후 파일을 다시 Read로 읽어 기대한 변경만 반영됐는지 확인.
5. 전체 수정 후 audit를 재실행해 위반이 사라졌는지 재검증.
