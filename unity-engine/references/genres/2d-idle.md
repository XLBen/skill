# 2D 放置 / 挂机游戏（Idle / Clicker）

## Contents
- 系统拆解 · 数值曲线 · 离线收益 · 生产循环 · 特有技巧 · 坑 · API 速查

## 核心系统拆解

点击/自动产出 → 货币积累 → 升级（产出倍率）→ 离线收益 → 数值膨胀 → 成就/转生。纯 UI 驱动为主（uGUI），数值公式设计是核心。

## 数值曲线（核心）

```csharp
// 文件: Assets/Scripts/Economy/EconomyConfig.cs — 数值集中一处
public static double CostOf(int level) => 100 * Math.Pow(1.15, level);   // 100 × 1.15^等级
public static double ProductionPerSecond() => BaseProduction * Math.Pow(2, Level) * GlobalMultiplier();

// 大数格式化: K/M/B/T/Qa 后缀
public static string FormatNumber(double value)
{
    string[] suffixes = { "", "K", "M", "B", "T", "Qa", "Qi" };
    int i = 0;
    while (value >= 1000 && i < suffixes.Length - 1) { value /= 1000; i++; }
    return value.ToString(i == 0 ? "0" : "0.#") + suffixes[i];
}
```

- 大数：double 不够用自研 BigNumber（mantissa + exponent）或 `System.Numerics.BigInteger`（IL2CPP 支持）

## 离线收益（核心）

```csharp
// 文件: Assets/Scripts/Economy/OfflineProgress.cs
// 存档记录最后在线时间戳(UTC, 防改时区白嫖)
void OnApplicationPause(bool paused)
{
    if (paused) SaveService.Save(new SaveData { lastSeen = DateTimeOffset.UtcNow.ToUnixTimeSeconds() });
}

void OnApplicationFocus(bool focus)
{
    if (focus) ApplyOfflineProgress();
}

void ApplyOfflineProgress()
{
    var save = SaveService.Load();
    long elapsed = DateTimeOffset.UtcNow.ToUnixTimeSeconds() - save.lastSeen;
    if (elapsed < minThresholdSeconds) return;               // 太短不算
    double capSeconds = Math.Min(elapsed, offlineCapHours * 3600);   // 离线收益上限(常见 8h)
    save.currency += ProductionPerSecond() * capSeconds;
    ShowOfflinePanel(elapsed, earnings);                     // 回来弹收益面板
    SaveService.Save(save);
    // 时间回拨检测: elapsed < 0 则忽略
}
```

## 自动化生产循环

```csharp
void Update()
{
    _tickTimer += Time.deltaTime;
    if (_tickTimer >= 0.1f)                     // 0.1s 结算一次(不逐帧)
    {
        _tickTimer = 0f;
        currency += ProductionPerSecond() * 0.1f;
        UpdateUI();                             // UI 节流刷新,数值变化才刷
    }
}
```

## 特有编程技巧

- **转生 Prestige**：重置进度换永久加成（×2 产出），长线目标
- **成就系统**：里程碑检测（达到 X 金币/点击 N 次）→ 全局加成
- **每日奖励**：登录日历（存 lastClaimDate），连续登录递进
- **反馈**：点击飘字（+1）、按钮弹性动画、货币数字滚动（显示值 Lerp 逼近真实值）
- **防作弊**：单机适度即可（存档校验和，`assets/templates/SaveService.cs`）；联网才需服务器验证

## 坑（现象 → 原因 → 解法）

1. double 溢出变科学计数 → 数值无上限设计 → 提前上 BigNumber/指数表示
2. 每帧刷新全部 UI 文本卡 → 无节流 → 节流 + 脏标记
3. 改时区白嫖离线收益 → 本地时间戳 → UTC Unix 时间戳
4. 升级成本公式散落 → 各处手写 → 集中 EconomyConfig
5. 闪退丢进度 → 只退出存档 → 关键升级/成就即时存档

**BAD/GOOD 示例（时间戳）：**

```csharp
// BAD: 本地时间,改系统时间就能刷收益
save.lastSeen = DateTime.Now;

// GOOD: UTC Unix 时间戳 + 回拨检测
save.lastSeen = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
if (elapsed < 0) return;   // 时间回拨忽略
```

## API 速查

| 类 | 关键成员 |
|---|---|
| `DateTimeOffset.UtcNow.ToUnixTimeSeconds` | 离线时间戳 |
| `Application-pause` | 退出存档时机 |
| `Math.Pow` | 成本曲线 |
| PlayerPrefs/JsonUtility | 存档 |

## 相关文件

- 存档：`references/00-techniques.md`、`assets/templates/SaveService.cs` · UI 节流：`references/12-performance-2d.md`

## 文档速查

- OnApplicationPause：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/MonoBehaviour.OnApplicationPause.html
- .NET DateTime：https://learn.microsoft.com/en-us/dotnet/api/system.datetime
