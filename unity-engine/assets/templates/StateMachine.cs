// StateMachine.cs — 类状态机模板(玩家/敌人 AI)
// 放 Assets/Scripts/Utils/StateMachine.cs;用法见 references/00-techniques.md
using UnityEngine;

public abstract class State<TContext> where TContext : MonoBehaviour
{
    protected readonly TContext Ctx;
    protected State(TContext ctx) => Ctx = ctx;

    public virtual void Enter() { }
    public virtual void Update() { }
    public virtual void FixedUpdate() { }
    public virtual void Exit() { }
}

public class StateMachine<TContext, TState>
    where TContext : MonoBehaviour
    where TState : State<TContext>
{
    public TState Current { get; private set; }
    private readonly TContext _ctx;

    public StateMachine(TContext ctx) => _ctx = ctx;

    /// <summary>切换状态;传 null 表示离开当前状态</summary>
    public void SwitchTo(TState next)
    {
        Current?.Exit();
        Current = next;
        Current?.Enter();
    }

    public void Update() => Current?.Update();
    public void FixedUpdate() => Current?.FixedUpdate();
}
