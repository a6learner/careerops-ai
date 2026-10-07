# CareerOps AI：MVP 规格说明（SWE 主线修订版）

## 文档信息

- 产品名称：CareerOps AI
- 文档类型：MVP Engineering and Product Specification
- 版本：v0.2（修订版，取代 v0.1）
- 目标周期：8–10 个有效开发周，每周约 12 小时
- 修订原因：v0.1 偏向“AI 求职助手”定位，容易被视为 LLM wrapper。v0.2 把后端工程确立为主线，AI 作为受严格约束的子系统
- 能力配比目标：后端与系统工程约 65%，AI 工程约 25%，前端约 10%

## 修订后的项目定位

CareerOps AI 是一个**以后端为核心的职位要求匹配服务**。系统把非结构化职位描述转换为结构化要求，将每条要求与用户真实经历建立可验证的证据关联，并通过异步任务、缓存、版本化数据和评估流水线保证结果稳定可追溯。

一句话定位：

> 这是一个后端系统工程项目，它恰好把 LLM 作为一个不可靠的外部依赖来治理。

面试主线不是“我做了一个 AI 应用”，而是：

1. 我如何设计数据模型和 API 契约。
2. 我如何处理异步、并发、幂等和失败恢复。
3. 我如何用缓存和索引控制延迟与成本。
4. 我如何验证一个概率性外部依赖的输出。
5. 我如何测量、测试和部署整个系统。

## SWE 能力对照表

每个后端能力都必须对应一个具体、可演示、可讲述的实现点。

| 后端能力 | 项目中的具体落点 | 面试可讲的深度 |
|---|---|---|
| API 设计 | REST 资源建模、状态码语义、分页、错误契约、版本前缀 | 为什么分析是子资源而不是动词端点 |
| 关系数据建模 | 8 张核心表、外键策略、唯一约束、软删除 | 为什么分析结果不可变而职位可变 |
| 索引与查询优化 | 列表页复合索引、EXPLAIN 前后对比 | 从 Seq Scan 到 Index Scan 的实测差异 |
| 事务 | 分析结果与证据行原子写入 | 为什么必须单事务提交，部分写入的后果 |
| 并发控制 | 唯一部分索引防止重复分析、乐观锁更新 | 竞态条件如何复现和验证 |
| 幂等性 | Idempotency-Key、任务去重键 | 用户双击提交和任务重投递如何处理 |
| 异步任务 | 队列、状态机、重试、退避、超时、死信 | 为什么 LLM 调用不能放在请求线程 |
| 缓存 | JD 解析结果缓存、列表查询缓存、缓存失效策略 | 缓存键设计与 stale 数据风险 |
| 限流与配额 | 按用户的分析次数限流、令牌桶 | 如何防止成本失控和滥用 |
| 认证授权 | 密码哈希、JWT 或会话、对象级授权 | 越权访问如何测试 |
| 可观测性 | 结构化日志、request_id、trace 贯穿异步任务、指标 | 一次失败分析如何端到端定位 |
| 测试 | 单元、集成、契约、并发、授权、AI 回归 | 如何测试一个不确定输出的系统 |
| 部署运维 | Docker、迁移、健康检查、配置分离、回滚 | 迁移失败与回滚策略 |
| 性能验证 | 负载测试、P50/P95、连接池调优 | 瓶颈定位过程 |

## 系统架构

### 组件边界

```
Client (Next.js)
    |
    v
API Service (FastAPI)
  - auth & authorization
  - resource CRUD
  - request validation
  - idempotency layer
  - rate limiter
  - job enqueue
    |
    +-----> PostgreSQL  (system of record, pgvector)
    |
    +-----> Redis       (cache, rate limit, queue broker)
    |
    v
Worker Service (Celery or Dramatiq)
  - parse pipeline
  - retrieval pipeline
  - claim validation
  - persistence
    |
    +-----> LLM Provider (OpenAI-compatible, via adapter)
```

关键设计约束：

- **API 服务永不直接调用 LLM。** 所有模型调用只发生在 Worker，保证 API 延迟可控且可测试。
- **Worker 不直接对外暴露端口。** 所有状态通过数据库和队列传递。
- **LLM 通过 adapter 接口访问。** 测试环境使用固定响应的 fake provider，使集成测试完全离线可运行。
- **PostgreSQL 是唯一事实来源。** Redis 中的任何数据都可以丢失并重建。

### 请求路径分类

| 路径类型 | 例子 | 延迟目标 | 是否调用 LLM |
|---|---|---:|---|
| 同步读 | 职位列表、经历列表、仪表盘 | P95 < 200ms | 否 |
| 同步写 | 创建职位、更新状态、创建任务 | P95 < 300ms | 否 |
| 异步提交 | 触发解析、触发分析 | P95 < 150ms | 否，仅入队 |
| 异步执行 | 解析、检索、匹配 | 分析 P95 < 30s | 是 |

这个分层本身就是一个后端设计论点：**用户可感知的交互必须与不可预测的外部依赖解耦。**

## 数据模型

### 表结构

以下为 MVP 全部表，字段省略常规审计列以外的次要项。

**users**

| 字段 | 类型 | 约束 |
|---|---|---|
| id | uuid | PK |
| email | citext | UNIQUE NOT NULL |
| password_hash | text | NOT NULL |
| created_at | timestamptz | NOT NULL |

**experiences**

| 字段 | 类型 | 约束 |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK users ON DELETE CASCADE |
| title | text | NOT NULL |
| kind | text | CHECK in (project, work, research, course, other) |
| description | text | NOT NULL |
| skills | text[] | NOT NULL DEFAULT '{}' |
| outcome | text | NULL |
| version | int | NOT NULL DEFAULT 1 |
| content_hash | text | NOT NULL |
| embedding | vector(1536) | NULL |
| deleted_at | timestamptz | NULL |

`content_hash` 用于判断经历是否真的改变，避免无意义的重嵌入和重分析。`version` 支持乐观锁。

**jobs**

| 字段 | 类型 | 约束 |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK users ON DELETE CASCADE |
| company | text | NOT NULL |
| title | text | NOT NULL |
| raw_description | text | NOT NULL |
| description_hash | text | NOT NULL |
| source_url | text | NULL |
| location | text | NULL |
| deadline | date | NULL |
| status | text | CHECK in (saved, preparing, applied, interview, offer, rejected, withdrawn) |
| version | int | NOT NULL DEFAULT 1 |
| deleted_at | timestamptz | NULL |

**job_requirements**

| 字段 | 类型 | 约束 |
|---|---|---|
| id | uuid | PK |
| job_id | uuid | FK jobs ON DELETE CASCADE |
| parse_run_id | uuid | FK parse_runs |
| category | text | CHECK in (must_have, nice_to_have, responsibility, education) |
| text | text | NOT NULL |
| skill_normalized | text | NULL |
| source_span_start | int | NULL |
| source_span_end | int | NULL |

`source_span_*` 指向 `jobs.raw_description` 的字符区间，使解析结果可回溯到原文，这是防幻觉的第一层结构保证。

**parse_runs** 与 **analysis_runs**

两者共享任务运行语义：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | 冗余存储以支持授权过滤 |
| job_id | uuid | FK jobs |
| status | text | queued, running, succeeded, failed, cancelled |
| idempotency_key | text | 去重键 |
| input_fingerprint | text | 输入内容哈希组合 |
| model_name | text | 使用的模型 |
| prompt_version | text | 提示词版本 |
| attempt | int | 重试次数 |
| error_code | text | 结构化错误码 |
| latency_ms | int | 执行耗时 |
| input_tokens / output_tokens | int | 成本核算 |
| started_at / finished_at | timestamptz | 时间戳 |

`analysis_runs` 一旦 succeeded 即**不可变**。重新分析创建新行，历史结果永久保留。这让“版本化领域数据”成为一个真实的设计决策，而不是口头概念。

**evidence_matches**

| 字段 | 类型 | 约束 |
|---|---|---|
| id | uuid | PK |
| analysis_run_id | uuid | FK analysis_runs ON DELETE CASCADE |
| requirement_id | uuid | FK job_requirements |
| experience_id | uuid | FK experiences, NULL 允许 |
| experience_version | int | 记录当时版本 |
| verdict | text | CHECK in (matched, partial, missing, insufficient_evidence) |
| quote | text | NULL |
| quote_valid | bool | NOT NULL |
| confidence | numeric(3,2) | NULL |

约束要点：`verdict = matched` 时 `experience_id` 和 `quote` 必须非空。这可以用表级 CHECK 约束表达，让**数据库本身拒绝无证据的正向断言**。这是一个很强的面试点：不变量应该尽可能下沉到最底层。

**action_items** 与 **analysis_feedback**

常规业务表，分别记录任务和用户反馈，`analysis_feedback` 关联到具体 `analysis_run_id` 与 `evidence_match_id`。

### 索引设计

必须实现并能解释的索引：

```sql
-- 职位列表主查询
CREATE INDEX idx_jobs_user_status_updated
  ON jobs (user_id, status, updated_at DESC)
  WHERE deleted_at IS NULL;

-- 防止同一输入的并发重复分析
CREATE UNIQUE INDEX uq_analysis_active
  ON analysis_runs (job_id, input_fingerprint)
  WHERE status IN ('queued', 'running');

-- 幂等键
CREATE UNIQUE INDEX uq_analysis_idem
  ON analysis_runs (user_id, idempotency_key);

-- 证据检索
CREATE INDEX idx_evidence_run
  ON evidence_matches (analysis_run_id, requirement_id);

-- 向量检索
CREATE INDEX idx_exp_embedding
  ON experiences USING hnsw (embedding vector_cosine_ops);
```

第二个索引是**用数据库约束解决并发问题**的典型案例，比应用层加锁更可靠。这类实现细节远比“我用了 Redis”更能体现工程判断。

## API 契约

### 资源端点

所有端点位于 `/api/v1` 之下。

| 方法与路径 | 说明 | 成功码 |
|---|---|---:|
| POST /auth/register | 注册 | 201 |
| POST /auth/login | 登录并签发令牌 | 200 |
| POST /auth/refresh | 刷新令牌 | 200 |
| GET /experiences | 分页列表 | 200 |
| POST /experiences | 创建 | 201 |
| GET /experiences/{id} | 详情 | 200 |
| PATCH /experiences/{id} | 更新，需 If-Match 版本 | 200 |
| DELETE /experiences/{id} | 软删除 | 204 |
| GET /jobs | 列表，支持 status、cursor、limit | 200 |
| POST /jobs | 创建 | 201 |
| GET /jobs/{id} | 详情，含最新解析与分析摘要 | 200 |
| PATCH /jobs/{id} | 更新 | 200 |
| DELETE /jobs/{id} | 软删除 | 204 |
| POST /jobs/{id}/parse-runs | 触发解析 | 202 |
| GET /jobs/{id}/parse-runs/{run_id} | 解析状态与结果 | 200 |
| POST /jobs/{id}/analysis-runs | 触发分析 | 202 |
| GET /jobs/{id}/analysis-runs | 分析历史列表 | 200 |
| GET /analysis-runs/{id} | 分析详情含证据 | 200 |
| POST /analysis-runs/{id}/feedback | 提交反馈 | 201 |
| GET /action-items | 任务列表 | 200 |
| POST /action-items | 创建任务，可来自建议 | 201 |
| PATCH /action-items/{id} | 更新状态 | 200 |
| GET /dashboard/summary | 聚合数据 | 200 |
| GET /healthz | 存活检查 | 200 |
| GET /readyz | PostgreSQL 与 Redis 依赖就绪检查 | 200 / 503 |

设计要点，全部需要能解释：

- **分析是子资源集合，不是 `POST /analyze` 动词端点。** 因为每次分析是一个有身份、有状态、可查询历史的实体。
- **异步触发返回 202 而不是 200。** 响应体包含 `run_id` 与 `status`，客户端轮询状态资源。
- **写操作使用 `Idempotency-Key` 请求头。** 重复提交返回同一 `run_id`，不产生第二次模型调用。
- **更新使用乐观锁。** 客户端携带 `If-Match: <version>`，版本冲突返回 409。
- **列表使用游标分页。** `cursor` 基于 `(updated_at, id)`，避免深分页 OFFSET 性能问题。

### 统一错误契约

```json
{
  "error": {
    "code": "ANALYSIS_RATE_LIMITED",
    "message": "Analysis quota exceeded for current window.",
    "details": {"retry_after_seconds": 43},
    "request_id": "01J8XA2C..."
  }
}
```

错误码为封闭枚举，前端按 code 分支，不解析 message 文本。`request_id` 与日志、trace 关联，是可观测性设计的一部分。

### 状态码语义

| 场景 | 状态码 |
|---|---:|
| 校验失败 | 422 |
| 未认证 | 401 |
| 越权访问他人资源 | 404（不泄露存在性） |
| 版本冲突 | 409 |
| 已有同输入分析在运行 | 409，返回既有 run_id |
| 超出配额 | 429，含 Retry-After |
| 上游模型不可用 | 503，任务保持可重试 |

## 异步任务设计

### 任务状态机

```
queued --> running --> succeeded
             |
             +--> failed (可重试)
             |
             +--> failed_permanent (校验失败或超出重试上限)
             |
             +--> cancelled
```

### 分析任务执行步骤

1. 领取任务，将 `status` 从 queued 更新为 running，写入 `started_at`。
2. 校验前置条件：解析结果存在、经历库非空。
3. 为每条要求执行检索，得到候选经历。
4. 调用 LLM 生成结构化匹配结果。
5. Schema 校验。
6. Claim 校验（见下节）。
7. 单事务写入 `analysis_runs` 结果与全部 `evidence_matches`。
8. 记录延迟、token、模型与提示词版本。
9. 失效相关缓存键。

### 可靠性策略

必须实现且能讲清的机制：

- **超时**：单次模型调用超时上限，整任务超时上限。
- **重试**：指数退避加抖动，仅对超时、限流、5xx 和格式错误重试；对校验失败不盲目重试。
- **重试上限**：达到上限进入 `failed_permanent`，写入结构化 `error_code`。
- **幂等执行**：任务体可能被投递多次，写入前检查终态，避免重复写入。
- **原子提交**：结果与证据行同事务，禁止出现有分析无证据的中间态。
- **worker 崩溃恢复**：running 超过阈值的任务由定时任务回收为 queued 或 failed。
- **成本保护**：单用户单窗口分析次数限流，超限直接拒绝入队。

**worker 崩溃恢复**这一项尤其值得实现，因为它体现你理解“任务不是函数调用，而是分布式状态”。

## 缓存策略

| 缓存对象 | 键 | 失效方式 | 收益 |
|---|---|---|---|
| JD 解析结果 | `parse:{description_hash}:{prompt_version}` | 提示词或模型版本变更 | 相同 JD 零成本复用 |
| 经历嵌入 | `emb:{content_hash}:{model}` | content_hash 变化 | 避免重复嵌入调用 |
| 仪表盘聚合 | `dash:{user_id}` | 写操作主动失效，TTL 兜底 | 减少多表聚合查询 |
| 限流计数 | `rl:{user_id}:{window}` | TTL 自然过期 | 成本与滥用控制 |

必须能回答的问题：缓存击穿如何处理，为什么用 content_hash 而不是 updated_at 作为键，缓存与数据库不一致时以谁为准。答案统一为：**PostgreSQL 为准，Redis 可随时清空重建。**

## AI 子系统（受约束的外部依赖）

AI 在本项目中被当作**输出不可信的第三方服务**，工程重点是治理而非智能。

### 三层防护

**第一层：Schema 约束**

模型必须返回预定义 JSON Schema。校验失败视为上游错误并重试，绝不写入半结构化数据。

**第二层：引用完整性校验**

程序化校验，不依赖模型自觉：

1. `experience_id` 是否存在，且属于当前用户。
2. `experience_version` 是否与当前一致。
3. `quote` 是否为对应经历文本的真实子串（归一化空白后比对）。
4. `verdict = matched` 时是否同时具备 id 与 quote。
5. 是否引用了未出现在检索候选集中的经历。

任一失败即拒绝该条结果，降级为 `insufficient_evidence`。

**第三层：数据库约束**

表级 CHECK 保证即使应用层出现 bug，也无法持久化无证据的正向断言。

### 评估流水线

- 固定标注集：50 条以上（要求，经历，期望 verdict）样例，脱敏后入库。
- 离线评估命令输出：citation validity、requirement coverage、unsupported claim rate、schema pass rate、P50/P95 延迟、每次分析估算 token。
- 提示词与模型版本记录在 `analysis_runs`，支持版本间对比。
- 提示词变更需重跑评估，结果差异记入仓库。

这让 AI 部分成为**可回归测试的模块**，而不是不可验证的黑盒。

## 前端范围（严格受限）

前端仅作为演示层，不投入过多时间。

页面清单：登录注册、仪表盘、职位列表、职位详情与分析、经历库、任务列表。

前端必须正确处理的工程行为：

- 异步任务轮询与状态展示（queued、running、failed 可重试）。
- 证据引用可点击回溯到经历原文。
- 409 版本冲突提示重新加载。
- 429 限流提示剩余等待时间。
- 空状态与错误状态。

不做：设计系统、动画体系、复杂表单向导、拖拽、移动端专门优化。

## P0 功能与验收标准

### P0-1 认证与对象级授权

- 邮箱密码注册登录，密码使用 bcrypt 或 argon2 哈希。
- 令牌签发与刷新，令牌过期可验证。
- 所有资源查询强制携带 `user_id` 过滤条件。

验收：

- Given 用户 A 登录，When 访问用户 B 的 job/experience/analysis-run，Then 一律返回 404。
- Given 令牌过期，When 调用受保护端点，Then 返回 401 且错误码为 `TOKEN_EXPIRED`。
- Given 存在自动化授权测试，When 运行测试套件，Then 覆盖全部资源类型的越权场景。

### P0-2 经历库与乐观锁

- CRUD 完整，软删除。
- 更新需携带 version，冲突返回 409。
- content_hash 变化时清除嵌入缓存并标记需重嵌入。

验收：

- Given 两个客户端持有同一 version，When 先后提交更新，Then 第二个返回 409 且数据未被覆盖。
- Given 经历内容未变仅重新保存，When 提交，Then content_hash 不变且不触发重新嵌入。
- Given 经历被软删除，When 查询列表，Then 不出现该记录，但历史分析中的引用仍可显示为已归档。

### P0-3 职位管理与游标分页

- CRUD 完整，状态机受 CHECK 约束。
- 列表支持 status 过滤与游标分页。
- 提供 EXPLAIN 前后对比记录，证明索引生效。

验收：

- Given 数据库中存在 5000 条职位，When 请求任意分页页码，Then P95 延迟低于 200ms。
- Given 使用游标翻页，When 期间插入新记录，Then 不出现重复或跳过记录。
- Given 索引被移除，When 运行性能测试，Then 能给出可对比的退化数据（作为文档证据）。

### P0-4 异步解析任务

- 202 提交，run 资源可查询。
- 幂等键与活跃唯一索引生效。
- 超时、重试、退避、永久失败、崩溃回收全部实现。

验收：

- Given 用户连续点击三次解析，When 请求携带同一 Idempotency-Key，Then 只创建一个 run 且只调用一次模型。
- Given 同一 JD 未变更，When 已有 succeeded 结果，Then 命中缓存或提示复用，不产生新模型调用。
- Given 模型返回非法 JSON，When 达到重试上限，Then run 变为 failed_permanent 且 error_code 明确。
- Given worker 在 running 中被强杀，When 回收任务运行，Then 该 run 被重新入队或标记失败，不会永久卡在 running。

### P0-5 证据匹配与三层校验

- 检索、匹配、校验、原子写入全链路完成。
- 违规引用降级而非丢弃整次分析。

验收：

- Given 模型引用不存在的 experience_id，When 校验执行，Then 该条降级为 insufficient_evidence 并记录校验失败计数。
- Given 模型 quote 不是经历原文子串，When 校验执行，Then quote_valid 为 false 且不作为 matched 证据。
- Given 写入过程中数据库异常，When 事务回滚，Then 不存在只有 analysis_run 而无 evidence_matches 的记录。
- Given 尝试直接向数据库插入 matched 且 experience_id 为空的行，When 执行 SQL，Then 被 CHECK 约束拒绝。

### P0-6 任务与仪表盘

- 建议转任务，任务 CRUD。
- 仪表盘聚合走缓存，写操作主动失效。

验收：

- Given 用户更新职位状态，When 立即查看仪表盘，Then 数据已反映变更（缓存已失效）。
- Given 关联职位被软删除，When 查看任务，Then 任务按既定规则保留并显示关联已归档，无数据库错误。

### P0-7 限流与配额

- 按用户滑动窗口限制分析次数。
- 超限返回 429 与 Retry-After。

验收：

- Given 用户在窗口内超出配额，When 再次触发分析，Then 返回 429 且未入队、未产生模型调用。
- Given 窗口结束，When 重新触发，Then 请求正常受理。

### P0-8 可观测性

- 结构化 JSON 日志，包含 request_id、user_id、run_id、attempt、latency、error_code。
- 初次投递的 request_id 通过队列传递到 worker；run_id 与 attempt 贯穿恢复后的完整生命周期。
- 关键指标可查询：任务成功率、重试率、P50/P95、token 消耗。

验收：

- Given 一次失败的分析，When 用 run_id 检索日志，Then 可串联 API 接收、入队、worker attempt、恢复与失败原因。
- Given 日志输出，When 检查内容，Then 不含密码、完整令牌或完整经历原文。

### P0-9 测试分层

必须存在的测试类别：

| 层级 | 内容 | 最低要求 |
|---|---|---|
| 单元 | 校验器、哈希、状态机、限流算法 | 核心逻辑分支覆盖 |
| 集成 | API + 真实 PostgreSQL（容器） | 全部 P0 端点 |
| 授权 | 跨用户越权矩阵 | 全资源类型 |
| 并发 | 并发触发分析、并发更新 | 唯一索引与乐观锁生效 |
| 契约 | 错误码与响应结构快照 | 全部错误码 |
| AI 回归 | 固定标注集评估 | 可重复执行并对比 |
| 负载 | 列表与详情端点压测 | 产出 P50/P95 报告 |

所有涉及 LLM 的测试使用 fake provider，保证 CI 离线、稳定、零成本。

### P0-10 部署与交付物

- Docker 化 API、worker、前端；Compose 启动本地依赖。
- 迁移由 Alembic 管理，可从空库执行，包含一次可演示的回滚。
- 健康检查区分 liveness 与 readiness；readiness 仅在 PostgreSQL 与 Redis
  均可访问时返回 200，否则返回 503 并标识失败依赖。
- CI 执行 lint、类型检查、测试、迁移检查。
- README 含问题定义、架构图、数据模型、API 摘要、关键设计决策、性能数据、已知限制。
- ADR 目录记录至少 5 个架构决策。
- 3–5 分钟 Demo 脚本。

验收：

- Given 全新环境，When 按 README 操作，Then 30 分钟内完成本地启动并跑通闭环。
- Given 生产部署，When 连续执行三次完整流程，Then 无需手工干预数据库。
- Given README 中的性能数字，When 追溯来源，Then 均对应保存的测试或评估输出。

## P1（MVP 稳定后）

- OAuth 登录
- 简历 PDF 解析生成经历草稿
- 全文搜索（PostgreSQL tsvector）
- 截止日期提醒
- 提示词与模型 A/B 对比面板
- CSV 导出
- 读写分离或连接池调优实验
- 更细粒度成本面板

第 7 个有效开发周仍未打通核心闭环时，全部 P1 自动延后。

## Non-goals

与 v0.1 一致并强化，明确不做：

- **自动投递与表单自动填写**：依赖不稳定第三方页面，合规风险高。
- **招聘网站大规模抓取**：仅支持用户粘贴 JD。
- **完整简历生成与排版**：不虚构技能、年限或成果。
- **自主多 Agent 工作流**：采用显式、可观察、可重试的管道。
- **社交与多人协作**：单用户数据边界。
- **企业 ATS 功能**：数据模型以求职者为中心。
- **邮件与日历集成**：MVP 内部维护截止日期。
- **移动 App 与实时协同**：仅响应式 Web，普通 HTTP。
- **模型微调与 GPU 推理集群**：仅通过 adapter 调用外部 API。
- **图数据库与知识图谱**：关系模型加向量检索足够。
- **单一匹配百分比**：只输出可解释的分项 verdict。
- **就业结果承诺**：只衡量系统自身可验证指标。
- **微服务拆分**：单体 API 加独立 worker 已足够；无真实规模需求时拆分只增加复杂度。这一条本身是一个可讲的架构判断。

## 指标设计

### 工程指标（简历主力）

- 列表与详情端点 P50/P95 延迟，索引优化前后对比
- 异步任务成功率、重试率、永久失败率
- 并发重复分析阻止率（应为 100%）
- 缓存命中率（JD 解析、嵌入、仪表盘）
- 集成测试与授权测试覆盖的端点比例
- 部署后错误率

### AI 质量指标

- Schema 通过率
- Citation validity rate
- Unsupported claim rate（校验拦截率）
- Requirement coverage
- 单次分析平均延迟与估算 token

### 产品闭环指标

- 新用户闭环完成率
- 建议转任务比例
- 分析反馈正向比例

先记录基线，再设定改进目标；任何对外数字必须有保存的输出文件支撑。

## 简历表达草案

技术栈行：

> Python, FastAPI, PostgreSQL (pgvector), Redis, Celery, Docker, pytest, GitHub Actions, Next.js

项目描述骨架（数字待实测替换）：

- Designed a versioned REST API with cursor pagination, optimistic concurrency (If-Match), and idempotent async job submission, cutting list-endpoint P95 latency from **A** ms to **B** ms via composite indexing.
- Built an asynchronous LLM pipeline with exponential-backoff retries, timeout handling, stale-task recovery, and partial-unique-index deduplication, eliminating duplicate model calls under concurrent submissions.
- Enforced evidence integrity through schema validation, citation verification against source text, and database CHECK constraints, reducing unsupported AI claims from **C**% to **D**% across **N** labeled requirement cases.
- Added Redis caching keyed by content hash for parse results and embeddings, achieving **E**% hit rate and reducing per-analysis model cost by **F**%.
- Instrumented end-to-end request tracing across API and workers with structured logging, enabling single-ID failure diagnosis.

## 范围控制规则

1. 删除后仍能完成核心闭环的功能不是 P0。
2. 新第三方集成、新数据库类型、新框架默认 P1 或更晚。
3. 无法评估的 AI 功能不进入 P0。
4. 新增超过半天的功能，必须删除或延后等量工作。
5. 考试周（第 6、11、15 周）只做测试、修复、文档与性能记录。
6. 第 7 个有效开发周功能冻结。
7. 每个新增后端机制必须能回答“它解决了哪个具体失败场景”，否则不做。

## 发布检查表

- [ ] 核心闭环线上可用
- [ ] 全部 P0 验收通过
- [ ] 越权测试矩阵通过
- [ ] 并发重复分析被阻止且有测试证明
- [ ] 乐观锁冲突返回 409 且有测试
- [ ] 幂等键防重复模型调用且有测试
- [ ] worker 崩溃回收可演示
- [ ] 事务原子性测试通过
- [ ] 三层证据校验全部生效，含 CHECK 约束验证
- [ ] 缓存命中率与失效逻辑有数据
- [ ] 限流返回 429 且有测试
- [x] Analysis run_id + attempt 贯穿 API、worker 与 recovery；初次 request_id 贯穿队列
- [ ] 迁移可从空库执行并演示一次回滚
- [ ] 负载测试报告已保存
- [ ] AI 评估集与评估输出已入库
- [ ] CI 全绿且离线可运行
- [ ] README、架构图、5 个 ADR、Demo 脚本完成
- [ ] 简历数字均可追溯到保存的输出

## 当前决策

CareerOps AI 的 MVP 目标是证明一件事：

> 作者能够设计并交付一个具备正确并发控制、事务边界、幂等语义、缓存策略、可观测性和测试分层的后端服务，并在其中安全地集成一个输出不可靠的 AI 依赖。

求职场景只是承载这些工程属性的业务外壳。任何无法强化上述工程主线或核心用户闭环的想法，默认不进入 MVP。
