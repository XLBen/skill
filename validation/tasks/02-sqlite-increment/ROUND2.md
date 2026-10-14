# 第二轮需求：批次校验与原子性

在已有的 event_ledger 上增加：

- 在写数据库前验证整个批次。任意一行 JSON 语法、字段集合、类型或空字符串无效，
  整批退出 `2`，stdout 为空，stderr 给出稳定错误类别和 1-based 行号，
  行号写成 `line <n>`（JSONL 第一行是 `line 1`）。
- 同一 `event_id` 已存在但 `account` 或 `delta` 不同属于 conflict（stderr 含 `conflict`），整批退出 `2`，
  stdout 为空，数据库不改变。
- 一个批次中先出现合法新事件、后出现无效事件时也必须原子回滚。
- 空 JSONL 是合法 semantic zero，成功输出
  `{"duplicates":0,"inserted":0}`。
- 只改 ingest 的校验和事务路径，report 不需要改动。
