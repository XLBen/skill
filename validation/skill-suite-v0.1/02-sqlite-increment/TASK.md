# Task: SQLite Event Ledger

构建一个 Python 3.10+、仅标准库的持久化事件账本：

```text
python src/event_ledger.py ingest --db <ledger.db> <events.jsonl>
python src/event_ledger.py report --db <ledger.db>
```

每个 JSONL 事件恰好包含：

```json
{"event_id":"e-1","account":"alpha","delta":5}
```

`event_id` 和 `account` 是非空字符串；`delta` 是 JSON integer，boolean 不算
integer。stdout 的 JSON 必须 compact、key 按字典序稳定排列。

## First Slice

- `ingest` 创建或复用 SQLite 数据库，导入全部合法事件。
- 数据跨进程持久化。
- 完全相同的 `event_id/account/delta` 再导入时是幂等 duplicate，不重复累计。
- 成功输出 `{"duplicates":<n>,"inserted":<n>}`。
- `report` 输出稳定的事件数和按 account 排序的总和：

  ```json
  {"account_totals":{"alpha":3,"beta":7},"event_count":3}
  ```

- 全新数据库的 report 是明确 semantic zero：

  ```json
  {"account_totals":{},"event_count":0}
  ```

- 首切片只处理合法输入和完全相同 duplicate；不要提前实现下面 SI-01。

## Planned Slice Increment SI-01

- 在写数据库前验证整个批次。任意一行 JSON 语法、字段集合、类型或空字符串无效，
  整批退出 `2`，stdout 为空，stderr 给出稳定错误类别和 1-based 行号。
- 同一 `event_id` 已存在但 `account` 或 `delta` 不同属于 conflict，整批退出 `2`，
  stdout 为空，数据库不改变。
- 一个批次中先出现合法新事件、后出现无效事件时也必须原子回滚。
- 空 JSONL 是合法 semantic zero，成功输出
  `{"duplicates":0,"inserted":0}`。
- SI-01 只影响 ingest 验证/事务路径，不得为仪式重放已通过且未受影响的 report 实现。

## Risk And Constraints

- 最大风险是假定 SQLite 唯一键、事务回滚和进程重开后的行为符合实现方案。
  Phase 0 应使用临时数据库做不超过 3 个命令的真实探针，保存原始结果并清理。
- profile 应为 `light`；首切片和 SI 分别声明预算。
- 产品代码只放 `src/`，验收测试由独立 test-author 放 `tests/`。
- 不使用第三方包、网络、ORM、迁移框架或后台服务。
