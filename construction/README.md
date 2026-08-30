# construction — 施工工程 skill（opencode）

把已通过答辩的论文（来自 [thesis-defense](../thesis-defense/)）改写成带验收命令的施工计划 `docs/PLAN.md`，然后严格串行执行：每步验收通过 → 打勾 → 下一步。验收失败自动分流：实现问题 vs 设计硬伤（登记变更单 CR-xx 回炉重辩）。

## 机制一览

- **门禁**：论文 status 非 passed/conditional 拒绝开工（stage gating）
- **改写映射**：论文 §4 待验证假设 → S0 技术验证步；§6 V-xx → 每步验收命令；§5 R-xx → 回退方案；§3 D-xx → 做法约束；§7 B-xx → 不做清单
- **执行循环**：SELECT→EXECUTE→VERIFY→TICK→LOG，默认连续施工、可随时暂停
- **防假打勾**：验收命令必须实际跑过才能改 `- [x]`；写不出命令的步骤必须拆分或标"人工验收"由用户确认
- **变更单回炉**：设计硬伤 → CR-xx → 切回 thesis-defense 重辩 → 更新计划复工
- **断点恢复**：状态只在 PLAN.md / build-log.md，会话死了重开从第一个未勾步骤继续
- **轻量差距吸收**：论文没说错、只是计划漏一小步（语义/边界/验收全不变）→ 追加步骤即可，不回炉；设计硬伤才走 CR（step-protocol）
- **竣工复盘**：从 defense-log 重发问题、build-log 重试与待议、变更单证伪对象里沉淀章程增补建议——这次的坑变成下次的 C-xx（retro-protocol）
- **竣工报告**：论文承诺 vs 实际交付对照表（P/D/A/R/V 编号 → S-xx → 状态）

## 目录结构

```
construction/
├── SKILL.md                     # 主入口（门禁、映射表、执行循环、铁律）
└── references/
    ├── plan-template.md         # PLAN.md 格式 + 步骤字段 + 验收占位规则 + 排序
    ├── step-protocol.md         # 单步协议 + 失败分流 + 轻量差距吸收 + 变更单 + 恢复细则
    └── retro-protocol.md        # 竣工复盘：章程增补建议三张清单
```

## 安装（项目级）

```powershell
Copy-Item -Recurse "本目录\construction" "<目标项目>\.opencode\skills\"
```

建议与 thesis-defense 一起安装（本 skill 依赖其产出的论文）。装完**重启 opencode**。

## 部署后自检

1. 在已通过答辩的项目里说"开工"：应生成 PLAN.md 并请求确认，确认后从 S0 连续施工
2. 中断会话后说"继续施工"：应从第一个未勾步骤恢复
3. 在未答辩的项目里说"施工"：应被门禁拒绝并指路 thesis-defense

## License

MIT
