// ObjectPool.cs — 通用组件对象池模板(弹幕/敌人/粒子/飘字)
// 放 Assets/Scripts/Utils/ObjectPool.cs;用法见 references/00-techniques.md
using System.Collections.Generic;
using UnityEngine;

public interface IPoolable
{
    void OnSpawn();
    void OnDespawn();
}

public class ObjectPool<T> where T : Component, IPoolable
{
    private readonly Queue<T> _pool = new();
    private readonly T _prefab;
    private readonly Transform _parent;

    /// <param name="prewarmCount">预热数量,避免首帧 Instantiate 卡顿</param>
    public ObjectPool(T prefab, int prewarmCount, Transform parent)
    {
        _prefab = prefab;
        _parent = parent;
        for (int i = 0; i < prewarmCount; i++)
            _pool.Enqueue(Create());
    }

    private T Create()
    {
        T obj = Object.Instantiate(_prefab, _parent);
        obj.gameObject.SetActive(false);
        return obj;
    }

    public T Get()
    {
        T obj = _pool.Count > 0 ? _pool.Dequeue() : Create();
        obj.gameObject.SetActive(true);
        obj.OnSpawn();
        return obj;
    }

    public void Return(T obj)
    {
        obj.OnDespawn();   // 先重置状态(速度/颜色/计时器)再隐藏
        obj.gameObject.SetActive(false);
        _pool.Enqueue(obj);
    }
}
