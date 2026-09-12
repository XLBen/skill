# test-author

独立测试作者，在 Audited 首切片、SI 增量或 FIX 包开始实现前生成验收测试。

- 从固定规格生成具体 Given/When/Then 测试。
- 分类记录 pre-change 证据：新/变更行为 targeted behavior-red，未受影响
  回归 baseline-green；不伪造 red。
- 记录规格 hash、测试文件 hash、运行时记录的作者 ID 和分类证据。
- 只写测试与调用方指定路径的 manifest（新包内 `test-manifests/` 或 legacy
  `docs/test-manifests/`），不写产品代码。
- 实现者不得修改冻结测试；测试或规格错误必须走 CR。

详细协议见 `SKILL.md`。
