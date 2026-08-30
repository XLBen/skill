---
project: demo-valid
thesis: docs/thesis.md @ v2 (passed)
created: 2026-08-30
status: building
---

# 施工计划：demo-valid

## 技术验证步（论文 §4 A-[待验证] → S0）

- [x] S0 验证 A-02：邮件周报占比 | 来源：A-02 | 产出：占比结论 | 验收：`python scripts/census.py` | 回退：假设不成立 → CR 回炉 2026-08-30

## 施工步骤

- [x] S1 存储层：建表与迁移 | 来源：P-01、V-01 | 产出：migrations/001.sql | 约束：D-01 | 验收：`npm test -- migrate` | 回退：R-01 2026-08-30
- [ ] S2 检索接口：全文索引查询 | 来源：P-01、V-02 | 产出：src/search.ts | 验收：`npm test -- search` | 回退：R-01 | 规模：半天

## 变更单（初始为空，施工中追加）

（无）
