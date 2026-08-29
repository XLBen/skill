// EventBus.cs — 静态事件总线模板(对象间解耦)
// 放 Assets/Scripts/Core/EventBus.cs;订阅者 OnEnable 订阅 / OnDisable 取消,防幽灵引用
// 用法见 references/13-architecture.md
using UnityEngine;

public static class EventBus
{
    public static event System.Action<int> OnScoreChanged;
    public static event System.Action<Vector3> OnEnemyDied;
    public static event System.Action<GameManager.GameState> OnGameStateChanged;

    public static void RaiseScoreChanged(int score) => OnScoreChanged?.Invoke(score);
    public static void RaiseEnemyDied(Vector3 pos) => OnEnemyDied?.Invoke(pos);
    public static void RaiseGameStateChanged(GameManager.GameState s) => OnGameStateChanged?.Invoke(s);
}
