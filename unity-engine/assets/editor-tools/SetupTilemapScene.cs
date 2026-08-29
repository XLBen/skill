// SetupTilemapScene.cs — 复制到 Assets/Editor/ 后菜单 Tools/UnitySkill/搭建 Tilemap 场景
// 用途: 创建 Grid + 地面/装饰/碰撞三层 Tilemap,碰撞层自动配 CompositeCollider2D 合并
using UnityEditor;
using UnityEngine;
using UnityEngine.Tilemaps;

public static class SetupTilemapScene
{
    [MenuItem("Tools/UnitySkill/搭建 Tilemap 场景")]
    public static void Run()
    {
        // Grid 容器
        var gridGo = new GameObject("Grid");
        var grid = gridGo.AddComponent<Grid>();
        grid.cellSize = new Vector3(1f, 1f, 0f);   // 与精灵 PPU=32 对应: 32px = 1 格

        // 地面层
        var ground = CreateLayer(gridGo.transform, "Ground", 0);
        // 装饰层
        var decor = CreateLayer(gridGo.transform, "Decor", 1);
        // 碰撞层: Static 刚体 + 复合碰撞合并
        var collision = CreateLayer(gridGo.transform, "Collision", 2);
        collision.AddComponent<TilemapCollider2D>();
        var rb = collision.AddComponent<Rigidbody2D>();
        rb.bodyType = RigidbodyType2D.Static;
        rb.compositeMode = CollisionCompositeMode2D.Collide;
        collision.AddComponent<CompositeCollider2D>();

        Debug.Log("Tilemap 场景搭建完成。在 Window > 2D > Tile Palette 中把精灵切块拖入后刷图。");
    }

    private static GameObject CreateLayer(Transform parent, string name, int order)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent);
        go.transform.localPosition = Vector3.zero;
        go.AddComponent<Tilemap>();
        var renderer = go.AddComponent<TilemapRenderer>();
        renderer.sortingOrder = order;   // 地面 0 < 装饰 1 < 碰撞 2
        return go;
    }
}
