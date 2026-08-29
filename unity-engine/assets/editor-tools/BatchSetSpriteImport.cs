// BatchSetSpriteImport.cs — 复制到 Assets/Editor/ 后菜单 Tools/UnitySkill/批量设置精灵导入
// 用途: 把选中文件夹(或 Assets/Art)下的所有图片批量改为 Sprite 导入,统一 PPU/过滤/压缩
using UnityEditor;
using UnityEngine;

public static class BatchSetSpriteImport
{
    // 按项目修改默认值: PPU=32 适合 32x32 像素美术,与图集一致
    private const float PixelsPerUnit = 32f;
    private const FilterMode Filter = FilterMode.Point;      // 像素风用 Point,其余 Bilinear
    private const TextureImporterCompression Compression = TextureImporterCompression.Uncompressed;

    [MenuItem("Tools/UnitySkill/批量设置精灵导入")]
    public static void Run()
    {
        string folder = "Assets/Art";
        string[] guids = AssetDatabase.FindAssets("t:Texture2D", new[] { folder });
        int changed = 0;

        foreach (string guid in guids)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            var importer = AssetImporter.GetAtPath(path) as TextureImporter;
            if (importer == null) continue;
            if (importer.textureType != TextureImporterType.Sprite)
            {
                importer.textureType = TextureImporterType.Sprite;
                importer.spriteImportMode = SpriteImportMode.Single;
                importer.spritePixelsPerUnit = PixelsPerUnit;
                importer.filterMode = Filter;
                importer.textureCompression = Compression;
                importer.mipmapEnabled = false;               // 2D 精灵一般不生成 mipmap
                importer.SaveAndReimport();
                changed++;
            }
        }

        AssetDatabase.SaveAssets();
        Debug.Log($"批量设置完成: {changed} 张图片已改为 Sprite (PPU={PixelsPerUnit})");
    }
}
