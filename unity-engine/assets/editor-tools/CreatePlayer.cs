// CreatePlayer.cs — 复制到 Assets/Editor/ 后菜单 Tools/UnitySkill/创建玩家
// 用途: 一键创建 2D 玩家对象(精灵/刚体/碰撞体/脚本槽位)
using UnityEditor;
using UnityEngine;

public static class CreatePlayer
{
    [MenuItem("Tools/UnitySkill/创建玩家")]
    public static void Run()
    {
        var go = new GameObject("Player");
        var sr = go.AddComponent<SpriteRenderer>();
        sr.sortingLayerName = "Default";

        var rb = go.AddComponent<Rigidbody2D>();
        rb.gravityScale = 1f;
        rb.constraints = RigidbodyConstraints2D.FreezeRotation;   // 2D 角色防摔倒
        rb.interpolation = RigidbodyInterpolation2D.Interpolate;  // 相机跟随不抖动

        var col = go.AddComponent<CapsuleCollider2D>();           // 圆角碰撞,无勾角卡墙

        go.tag = "Player";
        Selection.activeGameObject = go;
        Debug.Log("Player created. 请在 Inspector 设置精灵图并挂载控制脚本。");
    }
}
