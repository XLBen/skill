---
name: postgres
description: 设计或修改 Postgres 表结构、索引、查询、迁移、连接配置或行级安全（RLS）之前使用（包括 Supabase）。按影响从大到小列出要检查的规则。Postgres schema, query, connection and RLS rules to check before writing database code.
license: MIT
---

# Postgres：写数据库代码前对照一遍

按影响从大到小排列。每条都能在计划里变成一条验证（`EXPLAIN`、约束测试、迁移回滚测试）。
需要细节和 SQL 例子时，查 Postgres 官方文档或 Supabase 的 postgres best practices。

## 1. 查询与索引（影响最大）
- `WHERE`、`JOIN`、`ORDER BY` 经常用到的列要有索引；上线前对关键查询跑 `EXPLAIN (ANALYZE, BUFFERS)`，看到大表 `Seq Scan` 要说明原因。
- 外键列自己加索引（Postgres 不会自动建），否则删除父表行和关联查询都会慢。
- 复合索引：等值条件的列放前面，范围条件的列放后面。
- 只查一部分行时用部分索引（`WHERE deleted_at IS NULL`）；只读少数列时考虑覆盖索引（`INCLUDE`）。
- JSONB 查询用 GIN 索引；全文搜索用 `tsvector` + GIN，不要 `LIKE '%词%'`。

## 2. 连接
- 应用通过连接池访问（PgBouncer、Supabase 的 pooler）；连接数按数据库上限算，不要每个请求新建连接。
- 事务模式的连接池下，预编译语句（prepared statements）可能不可用，按驱动文档配置。
- 设置空闲超时，避免空闲连接占满上限。

## 3. 安全与 RLS
- 应用使用的数据库角色只给需要的权限，不用超级用户。
- 用 RLS 时：表上 `ENABLE ROW LEVEL SECURITY`；策略里用到的列要有索引；
  策略中的函数调用（例如 Supabase 的 `auth.uid()`）包成 `(select auth.uid())`，避免每行重复计算。

## 4. 表结构
- 主键：`bigint generated always as identity`，需要全局唯一或对外暴露时用 UUID（优先按时间有序的 UUIDv7）。
- 时间用 `timestamptz`；字符串用 `text`（需要长度限制就加 `CHECK`）；金额用 `numeric` 或整数分，不用浮点。
- **能用数据库约束表达的规则就写成约束**（`NOT NULL`、`UNIQUE`、`CHECK`、外键），不要只靠应用代码校验。
- 表名、列名全小写加下划线，不用需要加引号的名字。
- 数据量很大、按时间删除旧数据时才考虑分区。

## 5. 并发与锁
- 事务尽量短，不在事务里做网络请求或等待用户。
- 多个事务更新同一批行时按固定顺序加锁，避免死锁。
- 用表做任务队列时用 `SELECT ... FOR UPDATE SKIP LOCKED`。
- 需要跨进程互斥时用 advisory lock，而不是自建锁表。

## 6. 数据访问
- 避免 N+1：一次查出关联数据（`JOIN` 或 `WHERE id = ANY($1)`）。
- 大量写入用批量插入或 `COPY`，不要逐行提交。
- “有就更新、没有就插入”用 `INSERT ... ON CONFLICT`，不要先查再写。
- 分页用游标分页（`WHERE id > $last ORDER BY id LIMIT n`），大偏移量的 `OFFSET` 会越来越慢。

## 7. 迁移
- 每个迁移可以回滚，或者写明不能回滚的原因；改名、删列分两步走（先兼容新旧，再删除旧的），详见 `deprecation-and-migration`。
- 大表上建索引用 `CREATE INDEX CONCURRENTLY`；加带默认值的 `NOT NULL` 列前确认版本行为，避免长时间锁表。

## 8. 监控
- 开启 `pg_stat_statements` 找最慢、最频繁的查询；定期关注 autovacuum 和表膨胀。

（整理自 supabase/agent-skills 的 supabase-postgres-best-practices，MIT；用自己的话概括，未复制原文。）
