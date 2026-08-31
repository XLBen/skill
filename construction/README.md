# construction

这个 skill 从确认后的 PLAN 开始，不负责问需求，也不负责重新规划。

- `/build`：开始施工；每步都跑原始验收命令并保存证据。
- `/resume`：中断后重新校验并继续。
- `/change <fact>`：现实和契约不一致时建 CR，普通施工随即停止。
- `/finish`：最终对账和独立审计都通过后才置 done。
- `/retro`：竣工后复盘，可选。

PLAN 缺失或过期时，它会调用 contract-review 的 `/plan`，不会自己编一个。
执行与恢复细节见 `references/step-protocol.md`。
