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

## Required Behavior

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

- 这一轮只处理合法输入和完全相同的 duplicate。

## Constraints

- 只使用 Python 标准库；不使用 ORM、迁移框架、网络或后台服务。
- 产品代码只放 `src/`，测试放 `tests/`。`evaluation/` 是评测用的，不要读取。
