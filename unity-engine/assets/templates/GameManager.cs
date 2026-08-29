// GameManager.cs — 常驻游戏管理器单例模板
// 放 Assets/Scripts/Core/GameManager.cs,挂到 Boot 场景对象;用法见 references/13-architecture.md
using UnityEngine;

public class GameManager : MonoBehaviour
{
    public static GameManager Instance { get; private set; }

    public enum GameState { Boot, Menu, Playing, Paused, GameOver, Victory }
    public GameState State { get; private set; } = GameState.Boot;

    void Awake()
    {
        // 防重复实例: Boot 场景重复加载时不产生第二个管理器
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }
        Instance = this;
        DontDestroyOnLoad(gameObject);
    }

    public void ChangeState(GameState next)
    {
        if (State == next) return;
        State = next;
        Time.timeScale = next == GameState.Paused ? 0f : 1f;   // 暂停联动
        Debug.Log($"GameState -> {next}");
        // 通过事件广播给 UI/音频(见 references/13-architecture.md 事件解耦)
    }
}
