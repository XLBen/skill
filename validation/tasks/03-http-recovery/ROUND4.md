# 第四轮：上游 schema 变了

上游 API 变了：item 不再提供整数 `price_cents`，改为只含十进制数字的字符串 `price`；
其他字段和分页语义不变。请同时兼容 v1 和 v2：v2 的 `price` 要严格校验，并规范化成输出里的
整数 `price_cents`。同步失败时，旧的成功输出必须保持不变。
