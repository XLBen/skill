# Task: Resilient HTTP Catalog Mirror

构建一个 Python 3.10+、仅标准库的 HTTP catalog mirror：

```text
python src/catalog_sync.py --base-url <url> --output <catalog.json> [--max-pages N]
```

公开边界见 `boundary/API.md`。认证 token 只从环境变量 `CATALOG_TOKEN` 读取，
不得写入代码、日志或持久化文件。

## Required Behavior

- 使用运行中的真实 HTTP API，不用 mock 关闭真实边界验收。
- 带 `X-Client-Token` 请求 `/v1/catalog`。
- `--max-pages 1` 时获取第一个成功页面、严格验证 v1 item，并原子写 output。
- 429/503 属于可安全重试响应；每个页面最多 3 次 HTTP attempt，遵守
  `Retry-After`，没有该 header 时使用有界短退避。
- 成功时 stdout/stderr 均为空；output 文件是 UTF-8 compact JSON，以一个换行
  结束，递归 key 稳定，item 按 `id` 排序。
- 任意网络、认证、JSON 或 schema 失败必须非零退出、stdout 为空、stderr 给出
  稳定类别，且不得创建空 output 或覆盖旧的成功 output。
- 这一轮只做单页（`--max-pages 1`）；多页聚合和跨页去重在后续需求里。

服务处于 normal 场景时，首页面的输出应为：

```json
{"count":2,"items":[{"id":"p1","name":"Alpha","price_cents":100,"version":1},{"id":"p2","name":"Beta","price_cents":200,"version":1}]}
```

## Constraints

- 只使用 Python 标准库；不访问本地 benchmark server 之外的网络。
- 产品代码只放 `src/`，测试放 `tests/`。
- 服务由用户在另一个终端启动（`python boundary/server.py --port 8765`），token 是
  `CATALOG_TOKEN=benchmark-token`。以运行中的服务为准，不要读取或修改
  `evaluation/`、`boundary/server.py`、`boundary/control.py`、`boundary/transient_gate.py`。
