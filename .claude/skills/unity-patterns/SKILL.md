---
name: unity-patterns
description: Unity C# 코딩 패턴과 베스트 프랙티스
allowed-tools: Read, Write, Edit, Grep
model: claude-sonnet-4-20250514
---

# Unity 코딩 패턴

## MonoBehaviour 생명주기
```csharp
public class ExampleBehaviour : MonoBehaviour
{
    [SerializeField] private Rigidbody2D _rigidbody;
    
    private void Awake()
    {
        // 컴포넌트 초기화
        _rigidbody = GetComponent<Rigidbody2D>();
    }
    
    private void Start()
    {
        // 게임 로직 초기화
    }
    
    private void FixedUpdate()
    {
        // 물리 연산
    }
    
    private void Update()
    {
        // 프레임마다 실행
    }
}
```

## ScriptableObject 데이터
```csharp
[CreateAssetMenu(fileName = "NewItem", menuName = "Game/Item")]
public class ItemData : ScriptableObject
{
    public string ItemName;
    public Sprite Icon;
    public int Value;
}
```

## 이벤트 시스템
```csharp
public class GameEvents : MonoBehaviour
{
    public static UnityAction<int> OnScoreChanged;
    
    public static void TriggerScoreChange(int newScore)
    {
        OnScoreChanged?.Invoke(newScore);
    }
}
```

## Object Pooling
```csharp
public class ObjectPool : MonoBehaviour
{
    [SerializeField] private GameObject _prefab;
    private Queue<GameObject> _pool = new Queue<GameObject>();
    
    public GameObject Get()
    {
        if (_pool.Count > 0)
        {
            var obj = _pool.Dequeue();
            obj.SetActive(true);
            return obj;
        }
        return Instantiate(_prefab);
    }
    
    public void Return(GameObject obj)
    {
        obj.SetActive(false);
        _pool.Enqueue(obj);
    }
}
```