# 第二轮需求：多页同步

在已有的 catalog_sync 上增加：

- 不指定 `--max-pages` 时跟随 `next_cursor` 直到 `null`；最多 20 页，重复 cursor
  或超限必须失败且保留旧 output。
- 跨页重复 item `id` 选择最高 integer `version`；同版本内容冲突必须失败。
- 最终 output 只在所有页成功并通过 schema 验证后用同目录临时文件原子替换。
- normal 场景下最终是 3 个 item，`p2` 应为 version 2、name `Beta Prime`、
  `price_cents=250`。
