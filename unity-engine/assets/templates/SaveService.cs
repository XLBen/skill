// SaveService.cs — JSON 存档服务模板(含版本号与校验和)
// 放 Assets/Scripts/Core/SaveService.cs;用法见 references/00-techniques.md 存档系统
using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;

[Serializable]
public class SaveData
{
    public int schemaVersion = 1;          // 存档结构版本,结构变更时 +1 并写迁移
    public int level;
    public long coins;
    public float playTime;
    public string checksum = "";           // 简易防篡改
}

public static class SaveService
{
    private const string FileName = "save.json";

    public static string SavePath => Path.Combine(Application.persistentDataPath, FileName);

    public static void Save(SaveData data)
    {
        data.checksum = Checksum(data);    // 存校验和(不含自身)
        string json = JsonUtility.ToJson(data, prettyPrint: true);
        File.WriteAllText(SavePath, json);
    }

    public static SaveData Load()
    {
        if (!File.Exists(SavePath)) return new SaveData();
        try
        {
            var data = JsonUtility.FromJson<SaveData>(File.ReadAllText(SavePath));
            string sum = data.checksum;
            data.checksum = "";
            return Checksum(data) == sum ? data : new SaveData();   // 校验失败回新档
        }
        catch (Exception e)
        {
            Debug.LogWarning($"存档读取失败,使用新档: {e.Message}");
            return new SaveData();
        }
    }

    public static void Delete()
    {
        if (File.Exists(SavePath)) File.Delete(SavePath);
    }

    private static string Checksum(SaveData data)
    {
        string body = $"{data.schemaVersion}|{data.level}|{data.coins}|{data.playTime}";
        using var sha = SHA256.Create();
        byte[] hash = sha.ComputeHash(Encoding.UTF8.GetBytes(body));
        return Convert.ToBase64String(hash);
    }
}
