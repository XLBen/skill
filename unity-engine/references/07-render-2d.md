# 07 渲染：URP 2D Renderer（Unity 6.5）

## Contents
- 管线选择 · Light 2D · 混合样式 · 阴影 · 法线贴图 · 后处理 · 相机 · 材质 Shader · 坑

2D 项目推荐 **URP + 2D Renderer**（2D 光照/阴影/混合/后处理完整，移动端友好）。Built-in 无 2D 光照；HDRP 不适合 2D。

## 管线配置

Unity Hub 2D 模板默认带 URP + 2D Renderer；升级旧项目：创建 Pipeline Asset → Graphics 设置指认 → 创建 2D Renderer Data 加入 Renderer List（Render Pipeline Converter 可自动转材质）。

## Light 2D（2D 光照组件）

类型：`Freeform`（自定义形状）/ `Sprite`（按精灵轮廓）/ `Parametric`（参数化圆形/多边形）/ `Global`（全屏）/ `Point`。

| 属性 | 说明 |
|---|---|
| Intensity | 强度（>1 增亮） |
| Falloff | 衰减曲线 |
| Target Sorting Layers | 只照亮指定排序层 |
| Blend Style | 混合样式 |
| Shadows | 阴影开关（需 Shadow Caster 2D） |

**精灵受光条件**：材质必须是 2D 光照兼容 Shader（`Sprite-Lit-Default`/`Sprite-Unlit-Default`）；不受光的检查材质。来源：https://docs.unity3d.com/6000.5/Documentation/Manual/urp/2d-index.html

```csharp
Light2D light = GetComponent<Light2D>();
light.intensity = 1.2f;
light.color = Color.yellow;
```

## 混合样式与阴影

- **Blend Styles** 在 2D Renderer Data 定义（Lit 与 Multiply），Multiply 实现黑暗环境手电筒
- **ShadowCaster2D** 组件投射阴影（形状沿精灵轮廓）；阴影很耗性能，移动端限量（≤4 盏投影灯）

## 法线贴图

Sprite Editor 的 Secondary Textures 加 Normal Map（Texture Importer 生成），2D 光照下做立体感；Mask Map 控制受光区域。

## 后处理 Post-processing

URP Volume + Post-process Profile：Bloom、Vignette、Color Adjustments、Film Grain。像素风常用 Bloom（光效）+ Vignette（暗角）。

```csharp
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
if (volumeProfile.TryGet<ColorAdjustments>(out var ca)) { ca.saturation.value = 0.2f; }
```

## 相机设置（2D）

- 投影 Orthographic；`Size = 屏幕高像素 / (2 × PPU)`
- 像素风：Pixel Perfect Camera（com.unity.2d.pixel-perfect）
- 昼夜循环示例：

```csharp
void Update()
{
    float t = Mathf.PingPong(Time.time / cycleDuration, 1f);
    globalLight.color = Color.Lerp(dayColor, nightColor, t);
    globalLight.intensity = Mathf.Lerp(1f, 0.3f, t);
}
```

## 材质与 Shader

- 常用：`Universal Render Pipeline/2D/Sprite-Lit-Default`、`Sprite-Unlit-Default`
- 自定义 Shader Graph：2D 管线模板（Sprite Lit/Unlit Master Node）；特效（溶解/描边/闪白）用 Shader Graph 或改 MaterialPropertyBlock
- 深度 Shader 内容见 `references/99-doc-index.md` 的 Shader Graph 包链接

## 坑（现象 → 原因 → 解法）

1. 升级 URP 后材质变紫 → Built-in 材质未转 → Render Pipeline Converter 自动转换
2. 精灵不受光 → 材质不是 Sprite-Lit → 换 2D 光照兼容 Shader
3. 光不随相机移动 → Global/Freeform 光世界坐标与相机错位 → 检查光定位方式（Light Order/Localized）
4. 移动端发热 → 灯光/阴影超量 → 光 <10 盏非投影、阴影尽量不用
5. 像素风后处理模糊 → 后处理超采样设置不当 → 关闭抗锯齿类后处理/调 Render Scale

## 相关文件

- 精灵与排序：`references/03-2d-sprite.md` · 性能：`references/12-performance-2d.md`

## 文档速查

- URP 2D 光照：https://docs.unity3d.com/6000.5/Documentation/Manual/urp/2d-index.html
- Light2D API（URP 包）：https://docs.unity3d.com/Packages/com.unity.render-pipelines.universal@17.0/api/UnityEngine.Rendering.Universal.Light2D.html
- ShadowCaster2D API（URP 包）：https://docs.unity3d.com/Packages/com.unity.render-pipelines.universal@17.0/api/UnityEngine.Rendering.Universal.ShadowCaster2D.html
