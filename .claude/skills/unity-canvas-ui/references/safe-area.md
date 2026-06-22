# Safe Area 런타임 적용

모바일 기기의 노치, 펀치홀, 홈 인디케이터 영역을 피하려면 `Screen.safeArea`로 UI 컨테이너의 anchor를 런타임에 맞춰줘야 한다. 에디터에서도 Device Simulator의 safe area 표시를 참고해 디자인한다.

## 기본 스크립트

Canvas 바로 아래에 SafeArea RectTransform을 두고 이 스크립트를 붙인다.

```csharp
using UnityEngine;

[RequireComponent(typeof(RectTransform))]
[ExecuteAlways]
public class SafeAreaFitter : MonoBehaviour
{
    private RectTransform _rect;
    private Rect _lastSafeArea;
    private ScreenOrientation _lastOrientation;
    private Vector2Int _lastResolution;

    private void Awake()
    {
        _rect = GetComponent<RectTransform>();
        Apply();
    }

    private void Update()
    {
        // 해상도/방향 변경을 감지해 재적용
        if (Screen.safeArea != _lastSafeArea
            || Screen.orientation != _lastOrientation
            || new Vector2Int(Screen.width, Screen.height) != _lastResolution)
        {
            Apply();
        }
    }

    private void Apply()
    {
        var safe = Screen.safeArea;
        var anchorMin = safe.position;
        var anchorMax = safe.position + safe.size;

        anchorMin.x /= Screen.width;
        anchorMin.y /= Screen.height;
        anchorMax.x /= Screen.width;
        anchorMax.y /= Screen.height;

        _rect.anchorMin = anchorMin;
        _rect.anchorMax = anchorMax;
        _rect.offsetMin = Vector2.zero;
        _rect.offsetMax = Vector2.zero;

        _lastSafeArea = safe;
        _lastOrientation = Screen.orientation;
        _lastResolution = new Vector2Int(Screen.width, Screen.height);
    }
}
```

## 동작 설명

- `Screen.safeArea`는 픽셀 단위의 `Rect` (좌하단 기준).
- 이걸 화면 크기로 나누면 0~1 정규화 비율이 나와 바로 anchorMin/Max로 쓸 수 있다.
- `offsetMin/Max = 0`: 이 SafeArea RectTransform은 정확히 안전 영역만큼을 차지.
- 이 아래의 모든 UI는 자동으로 안전 영역 안에 들어간다 (부모가 안전 영역이므로).

## 주의 사항

- **UI가 절대 가려지면 안 되는 것**만 SafeArea 안에 넣는다. 배경 이미지 같은 건 SafeArea 밖(풀스크린 Canvas 바로 자식)에 두어야 화면 전체를 덮는다.
- `[ExecuteAlways]`로 에디터에서도 동작하지만, Unity 2019+의 Device Simulator를 함께 쓰면 노치 있는 기기를 모사할 수 있어 디자인이 편하다.
- 일부 Android 기기는 `Screen.safeArea`가 부정확하게 보고된다. 타겟 기기가 정해져 있으면 실기로 반드시 확인.

## Hierarchy 배치 예

```
Canvas (Scale With Screen Size, 1920x1080, Match 0.5)
├── Background (Image, full stretch, safe area 밖)
└── SafeArea (RectTransform + SafeAreaFitter)
    ├── HUD
    ├── ScreenRoot
    ├── ModalLayer
    └── ToastLayer
```

배경은 SafeArea 밖이라 화면 구석까지 채워지고, 실제 인터랙션/정보 UI는 SafeArea 안이라 노치 회피.
