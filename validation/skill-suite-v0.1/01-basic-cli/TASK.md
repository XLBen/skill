# Task: Receipt Totals CLI

构建一个无第三方依赖的 Python 3.10+ 命令行工具：

```text
python src/receipt_totals.py <input.csv>
```

输入是 UTF-8 CSV，表头必须严格为：

```text
receipt_id,category,amount_cents,status
```

## Required Behavior

- 每个 `receipt_id` 必须是非空且唯一的字符串。
- `category` 必须非空。
- `amount_cents` 必须是十进制非负整数，不接受小数、负数或空值。
- `status` 只能是 `paid`、`pending` 或 `refunded`。
- 只聚合 `paid` 行。
- 成功时 stdout 只输出一行 UTF-8 compact JSON，key 按字典序稳定排列：

  ```json
  {"accepted_count":3,"category_totals_cents":{"books":2500,"food":1500},"grand_total_cents":4000}
  ```

- `category_totals_cents` 的 category key 也按字典序排列。
- 合法文件没有 `paid` 行时属于明确的 semantic zero，必须成功输出：

  ```json
  {"accepted_count":0,"category_totals_cents":{},"grand_total_cents":0}
  ```

- 表头、字段、枚举或重复 ID 无效时退出码必须为 `2`，stdout 必须为空，stderr
  必须包含稳定错误类别和首个错误的 1-based 数据行号。
- 工具不得写文件、访问网络或改变输入。

## Constraints

- 只使用 Python 标准库。
- 产品实现只放在 `src/`。
- test-author 自行在 `tests/` 生成验收测试；不得复制或读取 owner oracle。
- 这是本地、可逆、需求明确的 direct 任务。没有实质外部假设，因此 Phase 0 应
  记录 `not-needed` 的理由，不得为了仪式伪造探针。
