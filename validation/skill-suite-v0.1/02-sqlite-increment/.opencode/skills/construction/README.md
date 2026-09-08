# construction

这个 skill 从确认后的 PLAN 开始，不负责问需求，也不负责重新规划。v0.1
首个切片或 SI 必须先由独立 test-author 生成并冻结验收测试。

- `/build`：开始施工；先接收冻结测试，每步都跑原始验收命令并保存证据。
- `/resume`：中断后重新校验并继续。
- `/change <fact>`：现实和契约不一致时建 CR，普通施工随即停止；计划内
  增量使用 SI。
- `/finish`：最终对账、MVP observation 和独立审计都通过后才置 done。
- `/retro`：竣工后复盘，可选。

PLAN 缺失或过期时，它会调用 contract-review 的 `/plan`，不会自己编一个。
执行、测试隔离、失败签名和恢复细节见 `references/step-protocol.md`。
