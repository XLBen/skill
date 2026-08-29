// CreateEnemyDataAssets.cs — 复制到 Assets/Editor/ 后菜单 Tools/UnitySkill/批量创建敌人数据
// 用途: 按名称清单批量生成 EnemyData ScriptableObject 资源(数据驱动敌人配置)
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public class EnemyData : ScriptableObject
{
    [Header("基础")]
    public int maxHealth = 100;
    public float moveSpeed = 3f;
    [Header("奖励")]
    public int expReward = 10;
    public int goldReward = 5;
}

public static class CreateEnemyDataAssets
{
    // 按项目敌人清单修改名称列表
    private static readonly List<string> EnemyNames = new()
    {
        "Slime", "Goblin", "Skeleton", "Bat", "Boss"
    };

    [MenuItem("Tools/UnitySkill/批量创建敌人数据")]
    public static void Run()
    {
        const string folder = "Assets/Data/Enemies";
        if (!Directory.Exists(folder)) Directory.CreateDirectory(folder);

        foreach (string name in EnemyNames)
        {
            string path = $"{folder}/{name}.asset";
            if (File.Exists(path)) { Debug.Log($"跳过已存在: {path}"); continue; }

            var data = ScriptableObject.CreateInstance<EnemyData>();
            data.name = name;
            AssetDatabase.CreateAsset(data, path);
        }

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
        Debug.Log($"敌人数据创建完成: {EnemyNames.Count} 个 (跳过已存在的)");
    }
}
