---
project: demo-invalid
thesis: thesis v2 passed
created: 2026-08-30
status: flying
---

# 施工计划：demo-invalid

## 技术验证步（论文 §4 A-[待验证] → S0）

- [x] S0 验证 | 来源：A-02

## 施工步骤

- [x] S1 存储层 | 来源：P-01 | 产出：migrations/001.sql
- [ ] S2 检索接口 | 来源：P-99、V-01 | 产出：src/search.ts | 验收：`npm test -- search`
- [x] S3 导出 | 来源：B-01 | 产出：src/export.ts | 验收：`npm test -- export` 2026-08-30
